import React from "react";
import { ResourceCard } from "./ResourceCard";

/**
 * NodeInspector — slide-in right-panel showing real-time diagnostics
 * for the selected node.
 *
 * Props:
 *   nodeId            — "ip:port" string or null (panel hidden when null)
 *   nodesInfo         — Object map of nodeId → node data (from graphData.nodes_info)
 *   onClose           — callback to deselect
 *   killedNodes       — Set<string> of manually/auto-killed node IDs
 */
export function NodeInspector({ nodeId, nodesInfo, onClose, killedNodes }) {
  const node = nodesInfo[nodeId];
  if (!node) return null;

  const appState = node.appState || {};
  const isKilled = node.isDead || killedNodes.has(nodeId);

  const cpu     = appState.cpu     ?? "0";
  const memory  = appState.memory  ?? "0";
  const network = appState.network ?? "0";
  const storage = appState.storage ?? "0";

  const isCpuFiltered     = appState._isCpuFiltered;
  const isMemoryFiltered  = appState._isMemoryFiltered;
  const isNetworkFiltered = appState._isNetworkFiltered;
  const isStorageFiltered = appState._isStorageFiltered;

  const activeNodeCount = node.active_target || Math.max((node.node_count || 1) - killedNodes.size, 1);
  const isConverged     = node.ic >= activeNodeCount && node.ic > 0;
  const isGossiping     = node.ic > 0 && !isConverged;

  const statusLabel = isKilled ? "TERMINATED" : isConverged ? "Converged" : isGossiping ? "Gossiping" : "Running";
  const statusColor = isKilled
    ? "text-red-500 bg-red-500/10 border-red-500/30"
    : isConverged
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
      : isGossiping
        ? "text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
        : "text-slate-400 bg-slate-700/30 border-slate-700/50";

  const nodeTotal    = node.totalMessages || 1;
  const nodeFiltered = node.filteredMessages || 0;
  const nodeSavings  = (nodeFiltered / nodeTotal) * 100;

  // CPU/memory icon helpers — defined inline to keep JSX readable
  const cpuIcon = (
    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
    </svg>
  );
  const memIcon = (
    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  );
  const netIcon = (
    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
    </svg>
  );
  const diskIcon = (
    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
    </svg>
  );

  const anyFiltered = isCpuFiltered || isMemoryFiltered || isNetworkFiltered || isStorageFiltered;

  return (
    <div
      className={`fixed top-0 right-0 h-full w-85 z-40 flex flex-col transition-transform duration-300 transform ${nodeId ? "translate-x-0" : "translate-x-full"}`}
      style={{
        background: "rgba(10, 15, 25, 0.92)",
        backdropFilter: "blur(24px)",
        borderLeft: "1px solid rgba(100, 116, 139, 0.2)",
        boxShadow: "-24px 0 64px rgba(0,0,0,0.8)",
      }}
    >
      {/* Header */}
      <div className="px-6 pt-8 pb-5 border-b border-white/5 flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${isKilled ? "bg-red-500" : isConverged ? "bg-emerald-500" : "bg-indigo-500"} animate-pulse`} />
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.25em]">
              {isKilled ? "Chaos Event Log" : "Node Diagnostic"}
            </p>
          </div>
          <p className="text-xl font-mono text-white font-bold break-all leading-tight">{nodeId}</p>
          <div className="flex items-center gap-3 mt-3">
            <span className={`inline-block text-[10px] font-black px-2.5 py-1 rounded border uppercase tracking-wider ${statusColor}`}>
              {statusLabel}
            </span>
            <div className="flex items-center gap-1.5 bg-slate-800/50 px-2.5 py-1 rounded-lg border border-slate-700/30">
              <span className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter">Savings:</span>
              <span className="text-[10px] font-mono font-bold text-emerald-400">{nodeSavings.toFixed(0)}%</span>
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="mt-1 w-8 h-8 rounded-xl flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all border border-transparent hover:border-white/20 active:scale-95"
          aria-label="Close node inspector"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6 custom-scrollbar space-y-8">
        {/* Resources */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-[10px] font-black text-cyan-400 uppercase tracking-[0.2em]">Real-Time Resources</h4>
            {anyFiltered && (
              <span className="text-[9px] text-amber-500/80 font-bold flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-amber-500 animate-pulse" /> VoI Active
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ResourceCard label="CPU Load"   value={cpu}     unit="%"    isFiltered={isCpuFiltered}     icon={cpuIcon}  />
            <ResourceCard label="Memory"     value={memory}  unit="%"    isFiltered={isMemoryFiltered}  icon={memIcon}  />
            <ResourceCard label="Bandwidth"  value={network} unit="Mbps" isFiltered={isNetworkFiltered} icon={netIcon}  />
            <ResourceCard label="Disk Usage" value={storage} unit="%"    isFiltered={isStorageFiltered} icon={diskIcon} />
          </div>
        </section>

        {/* Gossip Propagation */}
        <section className="bg-slate-900/40 rounded-2xl p-5 border border-white/5">
          <h4 className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] mb-4">Gossip Propagation</h4>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-xs text-slate-400 font-medium">Round Progress</span>
              <span className="text-xs font-mono font-bold text-white"># {node.round ?? 0}</span>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 transition-all duration-300" style={{ width: `${Math.min((node.round / 1000) * 100, 100)}%` }} />
            </div>
            <div className="grid grid-cols-2 gap-4 mt-6">
              <div>
                <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Discovered</p>
                <p className="text-sm font-mono font-bold text-white">
                  {Math.max(node.nd ?? 0, node.ic ?? 1)} <span className="text-[10px] font-normal text-slate-500">Nodes</span>
                </p>
              </div>
              <div>
                <p className="text-[9px] font-bold text-slate-500 uppercase mb-1">Convergence</p>
                <p className="text-sm font-mono font-bold text-white">
                  {Math.min(node.ic ?? 0, activeNodeCount)} / {activeNodeCount}
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="px-6 py-5 border-t border-white/5 bg-slate-950/50">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-mono text-slate-600">ID: {nodeId.split(":").pop()}</span>
          <span className="text-[9px] font-mono text-emerald-600 font-bold">LIVE STREAMING</span>
        </div>
      </div>
    </div>
  );
}
