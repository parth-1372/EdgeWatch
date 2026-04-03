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

      // Update gossip socket hook's ref immediately so links sever this frame
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
      setToast({ message: "Live experiment launched.", type: "success" });
    } catch (err) {
      setToast({ message: err.message, type: "error" });
    } finally {
      setBooting(false);
    }
  }, []);

  // ── Render ────────────────────────────────────────────────────────────────────
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
        <section className="space-y-6 mb-12 shrink-0">
          {loading ? (
            <div className="rounded-3xl bg-slate-900/40 border border-slate-800/20 p-12 flex flex-col items-center justify-center gap-4">
              <Spinner />
              <span className="text-xs font-mono text-slate-500 uppercase tracking-widest">Querying Node Config...</span>
            </div>
          ) : fetchError && !config ? (
            <div className="rounded-3xl bg-red-950/20 border border-red-500/20 p-12 flex flex-col items-center justify-center gap-4 text-center">
              <svg className="w-8 h-8 text-red-500/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="text-red-400 font-bold text-sm mb-1">Configuration Offline</p>
                <p className="text-red-500/60 font-mono text-[10px] uppercase tracking-wider">{fetchError}</p>
              </div>
              <button 
                onClick={fetchConfig}
                className="mt-2 px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-[10px] font-black uppercase tracking-widest border border-red-500/20 transition-all"
              >
                Retry Connection
              </button>
            </div>
          ) : config && (
            Object.entries(config).map(([sk, sd]) => (
              <SectionCard key={sk} sectionKey={sk} sectionData={sd} onChange={handleChange} />
            ))
          )}
        </section>

        {/* ── Live Topology Graph ───────────────────────────────────────────────── */}
        <section className="mb-12">
          <LiveTopologyGraph
            graphData={graphData}
            onSelectNode={setSelectedNodeId}
            killedNodes={killedNodes}
            pendingKills={pendingKills}
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



