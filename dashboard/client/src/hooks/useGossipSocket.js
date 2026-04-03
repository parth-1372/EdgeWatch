import { useState, useEffect, useRef, useCallback } from "react";
import { io } from "socket.io-client";

const SOCKET_URL = "http://localhost:5000";
const METRICS_FIELDS = ["cpu", "memory", "network", "storage"];

/**
 * useGossipSocket — manages the Socket.IO connection lifetime and all
 * live-graph state.
 *
 * Key fixes applied here:
 *
 * 1. STALE CLOSURE (CodeRabbit, Major):
 *    The vanilla `new_metric` handler closed over the initial empty `killedNodes`
 *    Set because `useEffect` captures values at render time and we used [].
 *    Solution: `killedNodesRef` is kept in sync with `killedNodes` state and is
 *    what the socket handler always reads.  No stale closure possible.
 *
 * 2. WEBSOCKET THROTTLING / STATE THRASHING:
 *    At 10-20 messages/sec per node the old code called setGraphData() on every
 *    event, hammering React's reconciler and causing continuous ForceGraph2D
 *    layout re-runs.  Solution: incoming events mutate only the mutable refs;
 *    a requestAnimationFrame loop (targeting ~60fps max) flushes into React
 *    state, batching all messages that arrived within one frame.
 */
export function useGossipSocket() {
  // ── mutable refs — hold the canonical state; never cause re-renders ─────────
  const nodesMapRef   = useRef(new Map());
  const linksSetRef   = useRef(new Set());
  const strikesMapRef = useRef(new Map());

  // killedNodesRef shadows the killedNodes state so socket handlers always
  // see the current set even though they live inside a [] effect.
  const killedNodesRef = useRef(new Set());

  // Signals that a flush is needed on the next animation frame
  const pendingFlushRef = useRef(false);
  const rafHandleRef    = useRef(null);

  // ── React state — only updated at frame rate ────────────────────────────────
  const [graphData, setGraphData] = useState({ nodes: [], links: [], nodes_info: {} });
  const [killedNodes, setKilledNodes]           = useState(new Set());
  const [globalTotalMessages, setGlobalTotal]   = useState(0);
  const [globalFilteredMessages, setGlobalFiltered] = useState(0);

  // Derived counters accumulated between flushes — using refs to avoid
  // capturing stale closure values in the RAF callback.
  const pendingTotalRef    = useRef(0);
  const pendingFilteredRef = useRef(0);

  // ── helpers ─────────────────────────────────────────────────────────────────

  /**
   * Flush the mutable refs into React state.  Called by the RAF loop so that
   * React re-renders happen at most once per animation frame, regardless of
   * how many socket messages arrived.
   */
  const flushToReact = useCallback(() => {
    const nodesMap = nodesMapRef.current;
    const linksSet = linksSetRef.current;
    const killedSet = killedNodesRef.current;

    // Build validated link list — sever any edge touching a dead/struck node
    const validLinks = Array.from(linksSet).map(k => {
      const [source, target] = k.split('->');
      return { source, target };
    }).filter(link => {
      const sStrikes = strikesMapRef.current.get(link.source) || 0;
      const tStrikes = strikesMapRef.current.get(link.target) || 0;
      const isSourceKilled = killedSet.has(link.source) || (nodesMap.get(link.source)?.isDead);
      const isTargetKilled = killedSet.has(link.target) || (nodesMap.get(link.target)?.isDead);
      return !isSourceKilled && !isTargetKilled && sStrikes < 3 && tStrikes < 3;
    });

    setGraphData({
      nodes: Array.from(nodesMap.values()),
      links: validLinks,
      nodes_info: Object.fromEntries(nodesMap),
    });

    // Flush accumulated message counters
    if (pendingTotalRef.current > 0 || pendingFilteredRef.current > 0) {
      setGlobalTotal(v => v + pendingTotalRef.current);
      setGlobalFiltered(v => v + pendingFilteredRef.current);
      pendingTotalRef.current    = 0;
      pendingFilteredRef.current = 0;
    }

    pendingFlushRef.current = false;
  }, []);

  /**
   * Schedule a single RAF flush.  Multiple calls within the same frame are
   * collapsed into one.
   */
  const scheduleFlush = useCallback(() => {
    if (pendingFlushRef.current) return;
    pendingFlushRef.current = true;
    rafHandleRef.current = requestAnimationFrame(flushToReact);
  }, [flushToReact]);

  // ── keep killedNodesRef in sync with killedNodes state ─────────────────────
  useEffect(() => {
    killedNodesRef.current = killedNodes;
  }, [killedNodes]);

  // ── socket lifecycle ────────────────────────────────────────────────────────
  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ["websocket"] });

    // ── run_started: full reset ──────────────────────────────────────────────
    socket.on("run_started", (p) => {
      // Cancel any pending RAF flush from the previous run
      if (rafHandleRef.current) cancelAnimationFrame(rafHandleRef.current);
      pendingFlushRef.current = false;

      nodesMapRef.current   = new Map();
      linksSetRef.current   = new Set();
      strikesMapRef.current = new Map();

      const newKilledSet = new Set();
      killedNodesRef.current = newKilledSet;
      setKilledNodes(newKilledSet);
      setGlobalTotal(0);
      setGlobalFiltered(0);
      pendingTotalRef.current    = 0;
      pendingFilteredRef.current = 0;

      const now = Date.now();
      const nodeCount = p.node_count || 1;
      (p.nodes || []).forEach(n => {
        const id = `${n.ip}:${n.port}`;
        nodesMapRef.current.set(id, {
          id, label: id, ic: 0, node_count: nodeCount, round: 0, nd: 0, rm: 0,
          bytes_of_data: 0, lastSeen: now,
          x: (Math.random() - 0.5) * 50, y: (Math.random() - 0.5) * 50,
          totalMessages: 0, filteredMessages: 0, appState: {}, isDead: false,
          strikes: 0,
        });
      });

      // Immediate flush for run_started (not rate-limited)
      setGraphData({
        nodes: Array.from(nodesMapRef.current.values()),
        links: [],
        nodes_info: Object.fromEntries(nodesMapRef.current),
      });
    });

    // ── new_metric: hot path — mutate refs only, schedule RAF flush ──────────
    socket.on("new_metric", (p) => {
      const senderKey = `${p.ip}:${p.port}`;
      const now = Date.now();
      const nodesMap   = nodesMapRef.current;
      const linksSet   = linksSetRef.current;
      const killedSet  = killedNodesRef.current; // ← ref, not stale closure

      let node = nodesMap.get(senderKey);
      if (!node) {
        node = {
          id: senderKey, label: senderKey,
          x: (Math.random() - 0.5) * 50, y: (Math.random() - 0.5) * 50,
          isDead: false, totalMessages: 0, filteredMessages: 0,
          appState: {}, strikes: 0,
        };
        nodesMap.set(senderKey, node);
      }

      // ── VoI savings tracking ─────────────────────────────────────────────
      let isFiltered = false;
      const fieldStats = {};

      METRICS_FIELDS.forEach(f => {
        const val = p[f];
        if (val === "not_updated") {
          isFiltered = true;
          // Preserve last known value for display; don't overwrite with sentinel
          fieldStats[f] = (node.appState?.[f] && node.appState[f] !== "not_updated")
            ? node.appState[f]
            : "not_updated";
        } else if (val !== undefined) {
          fieldStats[f] = val;
        }
      });

      pendingTotalRef.current++;
      if (isFiltered) pendingFilteredRef.current++;

      // ── Update node in-place (no object spread = no allocation churn) ────
      node.ic            = p.ic || 0;
      node.node_count    = p.node_count || 1;
      node.active_target = p.active_target || p.node_count || 1;
      node.round         = p.round || 0;
      node.nd            = p.nd || 0;
      node.rm            = p.rm || 0;
      node.bytes_of_data = p.bytes_of_data || 0;
      node.lastSeen      = now;
      node.totalMessages++;
      if (isFiltered) node.filteredMessages++;

      node.appState = {
        ...(node.appState || {}),
        ...fieldStats,
        cpu:     p.cpu     === "not_updated" ? (node.appState?.cpu     ?? "not_updated") : p.cpu,
        memory:  p.memory  === "not_updated" ? (node.appState?.memory  ?? "not_updated") : p.memory,
        network: p.network === "not_updated" ? (node.appState?.network ?? "not_updated") : p.network,
        storage: p.storage === "not_updated" ? (node.appState?.storage ?? "not_updated") : p.storage,
        _isCpuFiltered:     p.cpu     === "not_updated",
        _isMemoryFiltered:  p.memory  === "not_updated",
        _isNetworkFiltered: p.network === "not_updated",
        _isStorageFiltered: p.storage === "not_updated",
      };

      // ── Process peer topology ─────────────────────────────────────────────
      const peers      = p.data_stored_in_node || [];
      const peerStatus = p.peer_status || {};

      peers.forEach(peerKey => {
        if (typeof peerKey !== "string" || peerKey === senderKey) return;

        let targetDead = false;
        if (peerStatus[peerKey]) {
          const stats = peerStatus[peerKey];
          if (stats.failCount > 0) {
            const curStrikes = strikesMapRef.current.get(peerKey) || 0;
            strikesMapRef.current.set(peerKey, Math.max(curStrikes, stats.failCount));
          }
          if (stats.isAlive === false || stats.failCount >= 3) {
            targetDead = true;
          }
        }

        if (!nodesMap.has(peerKey)) {
          nodesMap.set(peerKey, {
            id: peerKey, label: peerKey, ic: 0, node_count: p.node_count || 1,
            round: 0, nd: 0, rm: 0, bytes_of_data: 0, lastSeen: now,
            x: (Math.random() - 0.5) * 100, y: (Math.random() - 0.5) * 100,
            appState: {}, isDead: false, totalMessages: 0, filteredMessages: 0,
            strikes: 0,
          });
        }

        const edgeA = `${senderKey}->${peerKey}`;
        const edgeB = `${peerKey}->${senderKey}`;

        if (targetDead) {
          linksSet.delete(edgeA);
          linksSet.delete(edgeB);
        } else {
          if (!linksSet.has(edgeA) && !linksSet.has(edgeB)) linksSet.add(edgeA);
        }
      });

      // ── Propagate strike counts; mark nodes dead ──────────────────────────
      let newKillsDetected = false;
      nodesMap.forEach(n => {
        const strikes = strikesMapRef.current.get(n.id) || 0;
        n.strikes = strikes;
        if (strikes >= 3 && !killedSet.has(n.id)) {
          killedSet.add(n.id);
          n.isDead = true;
          newKillsDetected = true;
        }
      });

      if (newKillsDetected) {
        // Update React state for killedNodes (triggers re-render for badges etc.)
        const nextSet = new Set(killedSet);
        killedNodesRef.current = nextSet;
        setKilledNodes(nextSet);
      }

      // Schedule a batched flush instead of setState on every message
      scheduleFlush();
    });

    return () => {
      socket.disconnect();
      if (rafHandleRef.current) cancelAnimationFrame(rafHandleRef.current);
    };
  }, [scheduleFlush]);  // scheduleFlush is stable (useCallback + no deps that change)

  // ── Kill node via Chaos Engine ───────────────────────────────────────────────
  const killNode = useCallback((nodeId) => {
    // Mark dead immediately in the ref so the next RAF flush severs links
    const nodesMap = nodesMapRef.current;
    if (nodesMap.has(nodeId)) {
      nodesMap.get(nodeId).isDead = true;
    }
    const nextSet = new Set(killedNodesRef.current).add(nodeId);
    killedNodesRef.current = nextSet;
    setKilledNodes(nextSet);
    scheduleFlush();
  }, [scheduleFlush]);

  return {
    graphData,
    killedNodes,
    globalTotalMessages,
    globalFilteredMessages,
    killNode,
  };
}
