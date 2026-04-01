import React from "react";
import { useState, useEffect, useCallback, useRef } from "react";
import { io } from "socket.io-client";
import ForceGraph2D from "react-force-graph-2d";

const API_BASE = "http://localhost:5000/api";
const SOCKET_URL = "http://localhost:5000";

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------
function isNumeric(val) {
  return !isNaN(parseFloat(val)) && isFinite(val);
}

function sectionLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Toast notification
// ---------------------------------------------------------------------------
function Toast({ message, type, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 3500);
    return () => clearTimeout(t);
  }, [onDismiss]);

  const base =
    "fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-4 rounded-xl shadow-2xl text-sm font-medium transition-all duration-300";
  const colours =
    type === "success"
      ? "bg-emerald-600 text-white border border-emerald-500"
      : "bg-red-600 text-white border border-red-500";

  return (
    <div className={`${base} ${colours}`}>
      {type === "success" ? (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      )}
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------
function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5 text-white"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Section card — renders one INI section dynamically
// ---------------------------------------------------------------------------
function SectionCard({ sectionKey, sectionData, onChange }) {
  const sectionMeta = {
    PriomonParam: { accent: "from-violet-500 to-indigo-600", dot: "bg-violet-400" },
    system_setting: { accent: "from-cyan-500 to-sky-600", dot: "bg-cyan-400" },
    database: { accent: "from-amber-500 to-orange-600", dot: "bg-amber-400" },
  };

  const meta = sectionMeta[sectionKey] || {
    accent: "from-slate-500 to-slate-700",
    dot: "bg-slate-400",
  };

  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/50 backdrop-blur-sm overflow-hidden shadow-xl">
      {/* Card header */}
      <div className={`bg-gradient-to-r ${meta.accent} px-6 py-4 flex items-center gap-3`}>
        <span className={`w-2.5 h-2.5 rounded-full ${meta.dot} shadow-lg`} />
        <h2 className="text-white font-semibold text-base tracking-wide font-mono">
          [{sectionKey}]
        </h2>
      </div>

      {/* Key-value fields */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        {Object.entries(sectionData).map(([key, value]) => {
          if (key.startsWith(";")) return null;

          const inputId = `${sectionKey}__${key}`;
          const strVal = value === null || value === undefined ? "" : String(value);

          return (
            <div key={key} className="flex flex-col gap-1.5">
              <label
                htmlFor={inputId}
                className="text-xs font-semibold text-slate-400 uppercase tracking-widest"
              >
                {sectionLabel(key)}
              </label>
              <input
                id={inputId}
                type="text"
                value={strVal}
                onChange={(e) => onChange(sectionKey, key, e.target.value)}
                className="
                  bg-slate-900/70 border border-slate-600/60 rounded-lg px-4 py-2.5
                  text-slate-100 text-sm font-mono placeholder-slate-600
                  focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500
                  transition-all duration-150
                "
                spellCheck={false}
                autoComplete="off"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Live Topology Graph component
// ---------------------------------------------------------------------------
function LiveTopologyGraph({ graphData, metricsLog, nodeCountMetadata }) {
  const graphRef = useRef();

  // Auto-center and configure forces when data arrived or node count changes
  // useEffect(() => {
  //   if (graphRef.current && graphData.nodes.length > 0) {
  //     const fg = graphRef.current;

  //     // Warm up and center the graph view
  //     fg.zoomToFit(400, 100);

  //     // Access the internal d3 simulation to fix the centering
  //     const simulation = fg.d3Simulation();
  //     if (simulation) {
  //       const centerForce = simulation.force('center');
  //       if (centerForce) {
  //         centerForce.x(0).y(0);
  //       }
  //     }
  //   }
  // }, [graphData.nodes.length]);
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      const fg = graphRef.current;

      // 1. Configure the D3 force correctly using d3Force
      const centerForce = fg.d3Force('center');
      if (centerForce) {
        centerForce.x(0).y(0);
      }

      // 2. Add a slight delay before zooming so coordinates are calculated
      setTimeout(() => {
        fg.zoomToFit(400, 100);
      }, 150);
    }
  }, [graphData.nodes.length]);
  // Paint nodes as gradient-filled circles with IP label
  const paintNode = useCallback((node, ctx, globalScale) => {
    const r = 8;
    const { ic, node_count } = node;

    // Status color mapping
    let color = "#64748b"; // Running (Gray)
    if (ic > 0) {
      color = ic >= node_count ? "#10b981" : "#6366f1"; // Converged (Emerald) : Gossiping (Indigo)
    }

    // Outer glow
    ctx.beginPath();
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
    ctx.fillStyle = `${color}22`; // Very transparent version for glow
    ctx.fill();

    // Main circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.3)";
    ctx.lineWidth = 1;
    ctx.stroke();

    // Label
    const labelSize = Math.max(10 / globalScale, 3);
    ctx.font = `${labelSize}px Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(226, 232, 240, 0.9)";
    ctx.fillText(node.label || node.id, node.x, node.y + r + 2);
  }, []);

  const nodeCount = graphData.nodes.length;
  const linkCount = graphData.links.length;

  return (
    <div className="rounded-3xl bg-slate-800/40 border border-slate-700/50 backdrop-blur-md overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-800/80 to-slate-900/80 px-8 py-5 flex items-center justify-between border-b border-slate-700/50">
        <div className="flex items-center gap-4">
          <div className="relative">
            <span className="absolute inset-0 rounded-full bg-emerald-500/20 blur-sm animate-pulse" />
            <span className="relative block w-3 h-3 rounded-full bg-emerald-500" />
          </div>
          <h2 className="text-slate-100 font-bold text-lg tracking-tight">
            Live Network Topology
          </h2>
        </div>
        <div className="flex items-center gap-6 text-slate-400 text-xs font-mono font-medium">
          <div className="bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-700/30">
            {nodeCount} Nodes
          </div>
          <div className="bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-700/30">
            {linkCount} Links
          </div>
          <div className="bg-slate-900/50 px-3 py-1.5 rounded-lg border border-slate-700/30">
            {metricsLog.length} Data Points
          </div>
        </div>
      </div>

      {/* Graph canvas */}
      <div className="relative" style={{ height: 500, background: "radial-gradient(circle at center, #1e293b 0%, #0f172a 100%)" }}>
        {nodeCount === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-slate-900/50 border border-slate-700/50 flex items-center justify-center animate-pulse">
                <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
              </div>
              <p className="text-slate-200 text-sm font-semibold">Awaiting Live Metrics</p>
              <p className="text-slate-500 text-xs mt-1 font-mono tracking-wide">Connect orchestrator to begin streaming</p>
            </div>
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeCanvasObject={paintNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.beginPath();
              ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            linkColor={() => "rgba(100, 116, 139, 0.25)"}
            linkWidth={1.5}
            linkDirectionalParticles={2}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={() => "rgba(56, 189, 248, 0.4)"}
            backgroundColor="transparent"
            // width={undefined}
            height={500}
            cooldownTicks={100}
            d3AlphaDecay={0.01}
            d3VelocityDecay={0.3}
          />
        )}
      </div>

      {/* Structured Metrics Table */}
      <div className="border-t border-slate-700/50 bg-slate-900/30">
        <div className="px-8 py-4 border-b border-slate-700/20">
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">
            Real-Time Node Diagnostics
          </h3>
        </div>
        <div className="max-h-[300px] overflow-y-auto overflow-x-hidden custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-slate-900/90 backdrop-blur-md text-[10px] text-slate-500 uppercase font-mono border-b border-slate-800">
              <tr>
                <th className="px-8 py-3 font-medium">Node Endpoint</th>
                <th className="px-4 py-3 font-medium">Round</th>
                <th className="px-4 py-3 font-medium">ND</th>
                <th className="px-4 py-3 font-medium">RM</th>
                <th className="px-4 py-3 font-medium">Data</th>
                <th className="px-4 py-3 font-medium">Convergence (IC)</th>
                <th className="px-4 py-3 font-medium text-right pr-8">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {Object.values(graphData.nodes_info || {}).sort((a, b) => b.lastSeen - a.lastSeen).map((node) => {
                const isConverged = node.ic >= node.node_count && node.ic > 0;
                const isGossiping = node.ic > 0 && !isConverged;

                return (
                  <tr key={node.id} className="hover:bg-slate-800/30 transition-colors duration-150">
                    <td className="px-8 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${isConverged ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : isGossiping ? 'bg-indigo-500 animate-pulse' : 'bg-slate-600'}`} />
                        <span className="text-slate-300 font-mono text-xs">{node.id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[10px] text-slate-400">
                      {node.round}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[10px] text-slate-400">
                      {node.nd}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[10px] text-slate-400">
                      {node.rm}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[10px] text-slate-400">
                      {node.bytes_of_data < 1024 ? `${node.bytes_of_data}B` : `${(node.bytes_of_data / 1024).toFixed(1)}KB`}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-3">
                        <div className="w-16 h-1 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ${isConverged ? 'bg-emerald-500' : 'bg-indigo-500'}`}
                            style={{ width: `${(node.ic / (node.node_count || 1)) * 100}%` }}
                          />
                        </div>
                        <span className="text-slate-400 font-mono text-[10px]">
                          {node.ic}/{node.node_count || '?'}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-right pr-8">
                      <span className={`
                        text-[9px] font-bold px-2 py-1 rounded uppercase tracking-tighter
                        ${isConverged ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' :
                          isGossiping ? 'bg-indigo-500/10 text-indigo-500 border border-indigo-500/20' :
                            'bg-slate-700/30 text-slate-500 border border-slate-700/50'}
                      `}>
                        {isConverged ? 'Converged' : isGossiping ? 'Gossiping' : 'Running'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {Object.keys(graphData.nodes_info || {}).length === 0 && (
            <div className="py-12 text-center text-slate-600 font-mono text-[10px] uppercase tracking-widest">
              Establishing node stream...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [booting, setBooting] = useState(false);
  const [toast, setToast] = useState(null);

  // Live metrics state
  const [graphData, setGraphData] = useState({ nodes: [], links: [], nodes_info: {} });
  const [metricsLog, setMetricsLog] = useState([]);
  const nodesMapRef = useRef(new Map());   // nodeId -> node object
  const linksSetRef = useRef(new Set());   // "srcId->tgtId" dedup keys

  // ---- Socket.io: connect and listen for live metrics ----------------------
  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ["websocket", "polling"] });

    // Handle experiment initialization
    socket.on("run_started", (initPayload) => {
      const now = Date.now();
      const initialNodesMap = new Map();
      const nodeCount = initPayload.node_count || 1;

      // Populate nodes as "Running"
      initPayload.nodes.forEach((node) => {
        const id = `${node.ip}:${node.port}`;
        initialNodesMap.set(id, {
          id,
          label: id,
          ic: 0,
          node_count: nodeCount,
          round: 0,
          nd: 0,
          rm: 0,
          bytes_of_data: 0,
          lastSeen: now,
          // Initial fuzzy position near center to prevent (0,0) sticking
          x: (Math.random() - 0.5) * 50,
          y: (Math.random() - 0.5) * 50
        });
      });

      nodesMapRef.current = initialNodesMap;
      linksSetRef.current = new Set();
      setMetricsLog([]);
      setGraphData({
        nodes: Array.from(initialNodesMap.values()),
        links: [],
        nodes_info: Object.fromEntries(initialNodesMap)
      });
    });

    socket.on("new_metric", (payload) => {
      const senderKey = `${payload.ip}:${payload.port}`;
      const now = Date.now();

      setMetricsLog((prev) => {
        const next = [...prev, payload];
        return next.length > 50 ? next.slice(-50) : next;
      });

      const nodesMap = nodesMapRef.current;
      const linksSet = linksSetRef.current;

      // Update or create reporter node
      let senderNode = nodesMap.get(senderKey);
      if (!senderNode) {
        senderNode = {
          id: senderKey,
          label: senderKey,
          x: (Math.random() - 0.5) * 50,
          y: (Math.random() - 0.5) * 50
        };
        nodesMap.set(senderKey, senderNode);
      }

      // Update data properties (IN PLACE to preserve physics x,y)
      Object.assign(senderNode, {
        ic: payload.ic || 0,
        node_count: payload.node_count || 1,
        round: payload.round || 0,
        nd: payload.nd || 0,
        rm: payload.rm || 0,
        bytes_of_data: payload.bytes_of_data || 0,
        lastSeen: now
      });

      const peers = payload.data_stored_in_node || [];
      peers.forEach((peerKey) => {
        if (peerKey === senderKey) return;

        if (!nodesMap.has(peerKey)) {
          nodesMap.set(peerKey, {
            id: peerKey,
            label: peerKey,
            ic: 0,
            node_count: payload.node_count || 1,
            round: 0,
            nd: 0,
            rm: 0,
            bytes_of_data: 0,
            lastSeen: now,
            x: (Math.random() - 0.5) * 100,
            y: (Math.random() - 0.5) * 100
          });
        }

        const edgeA = `${senderKey}->${peerKey}`;
        const edgeB = `${peerKey}->${senderKey}`;
        if (!linksSet.has(edgeA) && !linksSet.has(edgeB)) {
          linksSet.add(edgeA);
        }
      });

      const nodes = Array.from(nodesMap.values());
      const links = Array.from(linksSet).map((key) => {
        const [source, target] = key.split("->");
        return { source, target };
      });
      const nodes_info = Object.fromEntries(nodesMap);

      setGraphData({ nodes, links, nodes_info });
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // ---- Load config on mount ------------------------------------------------
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/config`);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const data = await res.json();
        setConfig(data);
      } catch (err) {
        setFetchError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ---- Field change handler ------------------------------------------------
  const handleChange = useCallback((section, key, value) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }));
  }, []);

  // ---- Save config ---------------------------------------------------------
  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Unknown error");
      setToast({ message: "Configuration saved successfully.", type: "success" });
    } catch (err) {
      setToast({ message: `Save failed: ${err.message}`, type: "error" });
    } finally {
      setSaving(false);
    }
  };

  // ---- Start experiment ----------------------------------------------------
  const handleStart = async () => {
    setBooting(true);
    try {
      const res = await fetch(`${API_BASE}/start`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Orchestrator error");
      setToast({ message: "Live network booted successfully!", type: "success" });
    } catch (err) {
      setToast({ message: `Boot failed: ${err.message}`, type: "error" });
    } finally {
      setBooting(false);
    }
  };

  // ---- Render loading / error states --------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 text-sm font-medium tracking-wide">
            Loading configuration…
          </p>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="bg-red-900/30 border border-red-700/50 rounded-2xl p-8 max-w-md text-center">
          <p className="text-red-400 font-semibold text-lg mb-2">Failed to load configuration</p>
          <p className="text-red-300/70 text-sm font-mono">{fetchError}</p>
          <p className="text-slate-500 text-xs mt-4">
            Is the API server running on <span className="text-slate-300 font-mono">localhost:5000</span>?
          </p>
        </div>
      </div>
    );
  }

  // ---- Main render ---------------------------------------------------------
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-violet-500/30">
      {/* Background radial glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-violet-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-[600px] h-[600px] bg-cyan-600/10 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-5xl mx-auto px-6 py-12">
        {/* --------------------------------------------------------------- */}
        {/* Header */}
        {/* --------------------------------------------------------------- */}
        <header className="mb-12">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
            </div>
            <span className="text-xs font-semibold tracking-[0.2em] text-violet-400 uppercase">
              PrioMon
            </span>
          </div>

          <h1 className="text-4xl font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent mt-3">
            Control Center
          </h1>
          <p className="text-slate-500 text-sm mt-1.5">
            Configure and launch the distributed monitoring network.
          </p>
        </header>

        {/* --------------------------------------------------------------- */}
        {/* Config section cards — dynamically rendered */}
        {/* --------------------------------------------------------------- */}
        <section className="space-y-6 mb-10">
          {Object.entries(config).map(([sectionKey, sectionData]) => {
            if (typeof sectionData !== "object" || sectionData === null) return null;
            return (
              <SectionCard
                key={sectionKey}
                sectionKey={sectionKey}
                sectionData={sectionData}
                onChange={handleChange}
              />
            );
          })}
        </section>

        {/* --------------------------------------------------------------- */}
        {/* Action bar */}
        {/* --------------------------------------------------------------- */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 mb-10">
          {/* Save button */}
          <button
            id="btn-save-config"
            onClick={handleSave}
            disabled={saving || booting}
            className="
              flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl
              bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-slate-500
              text-slate-100 font-semibold text-sm
              transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            {saving ? (
              <>
                <Spinner />
                Saving…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                Save Configuration
              </>
            )}
          </button>

          {/* Start experiment button */}
          <button
            id="btn-start-experiment"
            onClick={handleStart}
            disabled={booting || saving}
            className="
              relative flex-1 flex items-center justify-center gap-3
              px-10 py-4 rounded-xl font-bold text-base tracking-wide
              bg-gradient-to-r from-violet-600 to-indigo-600
              hover:from-violet-500 hover:to-indigo-500
              text-white shadow-xl shadow-violet-500/30
              hover:shadow-violet-500/50 hover:scale-[1.01]
              active:scale-[0.99]
              transition-all duration-200
              disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100
              disabled:shadow-violet-500/10
            "
          >
            {!booting && (
              <span className="absolute inset-0 rounded-xl ring-1 ring-violet-400/30 animate-pulse" />
            )}

            {booting ? (
              <>
                <Spinner />
                Booting Network…
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728M8.464 15.536a5 5 0 010-7.072m7.072 0a5 5 0 010 7.072M12 12h.01" />
                </svg>
                Start Experiment
              </>
            )}
          </button>
        </div>

        {/* --------------------------------------------------------------- */}
        {/* Live Network Topology Graph */}
        {/* --------------------------------------------------------------- */}
        <section className="mb-10">
          <LiveTopologyGraph graphData={graphData} metricsLog={metricsLog} />
        </section>

        {/* --------------------------------------------------------------- */}
        {/* Footer */}
        {/* --------------------------------------------------------------- */}
        <footer className="mt-16 text-center text-slate-700 text-xs">
          PrioMon Control Center · API on{" "}
          <span className="font-mono text-slate-600">:5000</span> · Orchestrator on{" "}
          <span className="font-mono text-slate-600">:4000</span>
        </footer>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Toast */}
      {/* ----------------------------------------------------------------- */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  );
}
