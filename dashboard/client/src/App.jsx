/**
 * App.jsx — PrioMon Control Center (thin orchestrator)
 *
 * All heavy lifting is delegated to:
 *   hooks/useGossipSocket  — WebSocket lifecycle, graph state, killedNodes ref fix
 *   hooks/useConfig        — config fetch / save
 *   components/*           — pure UI components
 *
 * Refactored from the monolithic 852-line version based on CodeRabbit & Senior
 * Engineer review feedback. See ADR in implementation_plan.md for full rationale.
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";

import { useGossipSocket }       from "./hooks/useGossipSocket";
import { useConfig }             from "./hooks/useConfig";
import { Toast }                 from "./components/Toast";
import { Spinner, GlobalEfficiencyBadge } from "./components/Spinner";
import { SectionCard }           from "./components/SectionCard";
import { NodeInspector }         from "./components/NodeInspector";
import { LiveTopologyGraph }     from "./components/LiveTopologyGraph";

const API_BASE = "http://localhost:5000/api";

/** Extract the IP portion from an "ip:port" string. */
function ipOnly(nodeId) {
  return nodeId ? nodeId.split(":")[0] : nodeId;
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
  const [booting, setBooting]         = useState(false);
  const [toast, setToast]             = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);

  // Fetch config on mount
  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  // ── Derived values ───────────────────────────────────────────────────────────
  const globalSavingsPercent = useMemo(() => {
    if (globalTotalMessages === 0) return 0;
    return (globalFilteredMessages / globalTotalMessages) * 100;
  }, [globalTotalMessages, globalFilteredMessages]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleKillNode = useCallback(async (nodeId) => {
    const ip   = ipOnly(nodeId);
    const port = nodeId.includes(":") ? nodeId.split(":")[1] : "";
    try {
      const res  = await fetch(`${API_BASE}/kill-node/${ip}/${port}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);

      // Update gossip socket hook's ref immediately so links sever this frame
      gossipKillNode(nodeId);
      setToast({ message: `⚡ Node ${ip} terminated. Gossip peers will detect failure within 3 rounds.`, type: "success" });
    } catch (err) {
      setToast({ message: err.message, type: "error" });
    }
  }, [gossipKillNode]);

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
      setToast({ message: "Live experiment launched.", type: "success" });
    } catch (err) {
      setToast({ message: err.message, type: "error" });
    } finally {
      setBooting(false);
    }
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center font-mono text-slate-500">
        <Spinner /> <span className="ml-3">Initializing Control Center...</span>
      </div>
    );
  }

  // Fetch failed — show error state instead of calling Object.entries(null)
  // (CodeRabbit finding: null config causes TypeError at render time)
  if (fetchError && !config) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center font-mono text-red-500">
        Failed to load configuration: {fetchError}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 selection:bg-violet-500/30 overflow-x-hidden">
      {/* Background décor */}
      <div className="fixed inset-0 pointer-events-none opacity-30 overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-600/20 rounded-full blur-[120px] -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-emerald-600/10 rounded-full blur-[120px] translate-y-1/2 -translate-x-1/2" />
      </div>

      <div className="relative max-w-6xl mx-auto px-8 py-12 flex flex-col min-h-[calc(100vh-6rem)]">

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6 shrink-0">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-xl shadow-indigo-500/20">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h1 className="text-3xl font-black tracking-tighter text-white">
                PRIOMON <span className="text-indigo-500">v1.2</span>
              </h1>
            </div>
            <p className="text-slate-500 max-w-md text-sm leading-relaxed font-medium">
              Distributed Monitoring Control Center with Value-of-Information (VoI) prioritized gossip.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <GlobalEfficiencyBadge savingsPercent={globalSavingsPercent} />
            <div className="bg-slate-900 px-4 py-2 rounded-xl border border-white/5 flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none">
                Stream Status: <span className="text-slate-100">Active</span>
              </span>
            </div>
          </div>
        </header>

        {/* ── Action buttons ──────────────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-12 shrink-0">
          <button
            id="btn-save-config"
            onClick={onSave}
            disabled={saving || booting || !config}
            className="w-full sm:w-auto px-8 py-4 rounded-2xl bg-slate-900 border border-white/10 hover:bg-slate-800 text-white font-bold text-sm transition-all shadow-lg active:scale-95 disabled:opacity-50"
          >
            {saving ? "Syncing..." : "Save Config"}
          </button>
          <button
            id="btn-boot-network"
            onClick={handleStart}
            disabled={booting}
            className="flex-1 px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-black text-sm tracking-wider shadow-2xl shadow-indigo-600/30 transition-all active:scale-95 disabled:opacity-50"
          >
            {booting ? "Provisioning..." : "BOOT DISTRIBUTED NETWORK"}
          </button>
        </div>

        {/* ── Config sections ──────────────────────────────────────────────────── */}
        {/* Guard against null config (CodeRabbit fix) before calling Object.entries */}
        {config && (
          <section className="space-y-6 mb-12 shrink-0">
            {Object.entries(config).map(([sk, sd]) => (
              <SectionCard key={sk} sectionKey={sk} sectionData={sd} onChange={handleChange} />
            ))}
          </section>
        )}

        {/* ── Live Topology Graph ───────────────────────────────────────────────── */}
        <section className="mb-12">
          <LiveTopologyGraph
            graphData={graphData}
            onSelectNode={setSelectedNodeId}
            killedNodes={killedNodes}
            onKillNode={handleKillNode}
            selectedNodeId={selectedNodeId}
          />
        </section>
      </div>

      {/* ── Node Inspector side panel ────────────────────────────────────────── */}
      {selectedNodeId && (
        <NodeInspector
          nodeId={selectedNodeId}
          nodesInfo={graphData.nodes_info}
          onClose={() => setSelectedNodeId(null)}
          killedNodes={killedNodes}
        />
      )}

      {/* ── Toast notifications ─────────────────────────────────────────────── */}
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
