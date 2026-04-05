/**
 * App.jsx — PrioMon Control Center
 *
 * All heavy lifting is delegated to:
 *   hooks/useGossipSocket  — WebSocket lifecycle, graph state
 *   hooks/useConfig        — config fetch / save
 *   components/*           — pure UI components
 */

import React, { useState, useEffect, useCallback, useMemo } from "react";

import { useGossipSocket } from "./hooks/useGossipSocket";
import { useConfig } from "./hooks/useConfig";
import { Toast } from "./components/Toast";
import { Spinner, GlobalEfficiencyBadge } from "./components/Spinner";
import { SectionCard } from "./components/SectionCard";
import { NodeInspector } from "./components/NodeInspector";
import { LiveTopologyGraph } from "./components/LiveTopologyGraph";

const API_BASE = (import.meta.env.VITE_API_BASE || "") + "/api";

/** Extract the IP portion from an "ip:port" string. */
function ipOnly(nodeId) {
  return nodeId ? nodeId.split(":")[0] : nodeId;
}

/** Format bytes to a human-readable string. */
function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

// ── Stat Card component ────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accentClass, iconPath, delay = 0 }) {
  return (
    <div
      className={`fade-in glass rounded-2xl p-5 flex items-start gap-4 border hover:border-white/10 transition-all duration-300 group`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${accentClass} transition-transform duration-300 group-hover:scale-110`}>
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
        </svg>
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-1">{label}</p>
        <p className="text-xl font-mono font-black text-white truncate stat-value">{value}</p>
        {sub && <p className="text-[10px] text-slate-600 font-medium mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function App() {
  // ── Hooks ───────────────────────────────────────────────────────────────────
  const {
    graphData,
    killedNodes,
    globalTotalMessages,
    globalFilteredMessages,
    killNode: gossipKillNode,
  } = useGossipSocket();

  const {
    config,
    loading,
    fetchError,
    saving,
    fetchConfig,
    handleChange,
    handleSave,
  } = useConfig();

  // ── Local UI state ───────────────────────────────────────────────────────────
  const [booting, setBooting] = useState(false);
  const [toast, setToast] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [pendingKills, setPendingKills] = useState(new Set());

  // Fetch config on mount
  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  // ── Derived values ───────────────────────────────────────────────────────────
  const globalSavingsPercent = useMemo(() => {
    if (globalTotalMessages === 0) return 0;
    return (globalFilteredMessages / globalTotalMessages) * 100;
  }, [globalTotalMessages, globalFilteredMessages]);

  const activeNodeCount = useMemo(() => {
    return graphData.nodes.filter(n => !killedNodes.has(n.id)).length;
  }, [graphData.nodes, killedNodes]);

  const totalRounds = useMemo(() => {
    const nodes = Object.values(graphData.nodes_info || {});
    if (nodes.length === 0) return 0;
    return Math.max(...nodes.map(n => n.round ?? 0));
  }, [graphData.nodes_info]);

  const totalDataBytes = useMemo(() => {
    return Object.values(graphData.nodes_info || {}).reduce((acc, n) => acc + (n.bytes_of_data || 0), 0);
  }, [graphData.nodes_info]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleKillNode = useCallback(async (nodeId) => {
    if (pendingKills.has(nodeId)) return;

    setPendingKills(prev => new Set(prev).add(nodeId));
    const ip = ipOnly(nodeId);
    const port = nodeId.includes(":") ? nodeId.split(":")[1] : "";
    try {
      const res = await fetch(`${API_BASE}/kill-node/${ip}/${port}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);

      gossipKillNode(nodeId);
      setToast({ message: `⚡ Node ${ip} terminated. Gossip peers will detect failure within 3 rounds.`, type: "success" });
    } catch (err) {
      setToast({ message: err.message, type: "error" });
    } finally {
      setPendingKills(prev => {
        const next = new Set(prev);
        next.delete(nodeId);
        return next;
      });
    }
  }, [gossipKillNode, pendingKills]);

  const onSave = useCallback(() => {
    handleSave(
      msg => setToast({ message: msg, type: "success" }),
      msg => setToast({ message: msg, type: "error" }),
    );
  }, [handleSave]);

  const handleStart = useCallback(async () => {
    setBooting(true);
    try {
      const res = await fetch(`${API_BASE}/start`, { method: "POST" });
      if (!res.ok) throw new Error("Orchestrator unreachable");
      setToast({ message: "🚀 Distributed experiment launched.", type: "success" });
    } catch (err) {
      setToast({ message: err.message, type: "error" });
    } finally {
      setBooting(false);
    }
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 selection:bg-violet-500/30 overflow-x-hidden">

      {/* ── Ambient background glows ─────────────────────────────────────────── */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[700px] h-[700px] bg-indigo-600/10 rounded-full blur-[140px] -translate-y-1/3 translate-x-1/3" />
        <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-emerald-600/8 rounded-full blur-[140px] translate-y-1/3 -translate-x-1/3" />
        <div className="absolute top-1/2 left-1/2 w-[400px] h-[400px] bg-violet-600/5 rounded-full blur-[100px] -translate-x-1/2 -translate-y-1/2" />
      </div>

      <div className="relative max-w-6xl mx-auto px-6 lg:px-8 py-10 flex flex-col gap-10">

        {/* ── Header ───────────────────────────────────────────────────────────── */}
        <header className="fade-in flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div>
            {/* Logo + Name */}
            <div className="flex items-center gap-3 mb-3">
              <div className="relative">
                <div className="absolute inset-0 bg-indigo-500/40 rounded-2xl blur-md" />
                <div className="relative w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-xl">
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-black tracking-tight text-white leading-none">
                  PRIO<span className="gradient-text-indigo">MON</span>
                </h1>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.25em] mt-0.5">Control Center</p>
              </div>
            </div>
            <p className="text-slate-500 text-sm leading-relaxed max-w-sm">
              Distributed monitoring via VoI-prioritized gossip protocol with real-time fault detection.
            </p>
          </div>

          {/* Status pill + efficiency badge */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <GlobalEfficiencyBadge savingsPercent={globalSavingsPercent} />
            <div className="glass px-4 py-2 rounded-xl flex items-center gap-2.5">
              <div className="relative">
                <div className="absolute inset-0 bg-emerald-500 rounded-full animate-ping-slow opacity-60" />
                <div className="relative w-2 h-2 rounded-full bg-emerald-400" />
              </div>
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Stream <span className="text-slate-100">Live</span>
              </span>
            </div>
          </div>
        </header>

        {/* ── Stats Bar ────────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Active Nodes"
            value={activeNodeCount}
            sub={killedNodes.size > 0 ? `${killedNodes.size} terminated` : "All healthy"}
            accentClass="bg-indigo-500/10 text-indigo-400"
            iconPath="M5 12h14M12 5l7 7-7 7"
            delay={0}
          />
          <StatCard
            label="VoI Efficiency"
            value={`${globalSavingsPercent.toFixed(1)}%`}
            sub="Bandwidth saved"
            accentClass="bg-emerald-500/10 text-emerald-400"
            iconPath="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            delay={80}
          />
          <StatCard
            label="Gossip Rounds"
            value={totalRounds.toLocaleString()}
            sub="Max across cluster"
            accentClass="bg-violet-500/10 text-violet-400"
            iconPath="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            delay={160}
          />
          <StatCard
            label="Data Transferred"
            value={formatBytes(totalDataBytes)}
            sub="Across all nodes"
            accentClass="bg-cyan-500/10 text-cyan-400"
            iconPath="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
            delay={240}
          />
        </div>

        {/* ── Action Bar ───────────────────────────────────────────────────────── */}
        <div className="fade-in fade-in-delay-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <button
            id="btn-save-config"
            onClick={onSave}
            disabled={saving || booting || !config}
            className="sm:w-auto px-6 py-3.5 rounded-xl glass border border-white/8 hover:bg-white/5 hover:border-white/15 text-white font-bold text-sm transition-all duration-200 shadow-md active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {saving ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Syncing...
              </span>
            ) : "Save Config"}
          </button>
          <button
            id="btn-boot-network"
            onClick={handleStart}
            disabled={booting}
            className="flex-1 px-6 py-3.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-black text-sm tracking-wider shadow-2xl shadow-indigo-700/30 transition-all duration-200 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden group"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/5 to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            {booting ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Provisioning Network...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                BOOT DISTRIBUTED NETWORK
              </span>
            )}
          </button>
        </div>

        {/* ── Config Sections ───────────────────────────────────────────────────── */}
        <section className="fade-in fade-in-delay-3 space-y-4">
          <h2 className="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em] mb-5 flex items-center gap-3">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent to-slate-800" />
            Cluster Configuration
            <div className="h-px flex-1 bg-gradient-to-l from-transparent to-slate-800" />
          </h2>

          {loading ? (
            <div className="glass rounded-3xl p-16 flex flex-col items-center justify-center gap-5">
              <div className="relative">
                <div className="absolute inset-0 bg-indigo-500/20 rounded-full blur-xl animate-pulse" />
                <Spinner />
              </div>
              <div className="text-center">
                <p className="text-xs font-mono text-slate-500 uppercase tracking-widest">Querying Node Config</p>
                <p className="text-[10px] text-slate-700 mt-1">Connecting to orchestrator...</p>
              </div>
            </div>
          ) : fetchError && !config ? (
            <div className="glass rounded-3xl border border-red-500/20 p-16 flex flex-col items-center justify-center gap-5 text-center">
              <div className="w-14 h-14 rounded-2xl bg-red-500/10 flex items-center justify-center border border-red-500/20">
                <svg className="w-7 h-7 text-red-500/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <p className="text-red-400 font-bold text-sm mb-1">Orchestrator Offline</p>
                <p className="text-red-500/50 font-mono text-[11px]">{fetchError}</p>
              </div>
              <button
                onClick={fetchConfig}
                className="px-5 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-bold uppercase tracking-widest border border-red-500/20 transition-all active:scale-95"
              >
                Retry Connection
              </button>
            </div>
          ) : config && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(config).map(([sk, sd]) => (
                <SectionCard key={sk} sectionKey={sk} sectionData={sd} onChange={handleChange} />
              ))}
            </div>
          )}
        </section>

        {/* ── Live Topology Graph ───────────────────────────────────────────────── */}
        <section className="fade-in fade-in-delay-4">
          <LiveTopologyGraph
            graphData={graphData}
            onSelectNode={setSelectedNodeId}
            killedNodes={killedNodes}
            pendingKills={pendingKills}
            onKillNode={handleKillNode}
            selectedNodeId={selectedNodeId}
          />
        </section>

        {/* ── Footer ───────────────────────────────────────────────────────────── */}
        <footer className="text-center py-4 border-t border-white/5">
          <p className="text-[10px] font-mono text-slate-700 tracking-widest uppercase">
            PrioMon v1.2 · Distributed Gossip Monitoring · MIT License
          </p>
        </footer>

      </div>

      {/* ── Node Inspector side panel ─────────────────────────────────────────── */}
      {selectedNodeId && (
        <NodeInspector
          nodeId={selectedNodeId}
          nodesInfo={graphData.nodes_info}
          onClose={() => setSelectedNodeId(null)}
          killedNodes={killedNodes}
        />
      )}

      {/* ── Toast notifications ───────────────────────────────────────────────── */}
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
