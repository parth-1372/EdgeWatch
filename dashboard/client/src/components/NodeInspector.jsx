import React from "react";
import { ResourceCard } from "./ResourceCard";

/**
 * NodeInspector — slide-in right-panel showing real-time diagnostics
 * for the selected node.
 *
 * Props:
 *   nodeId            — "ip:port" string
 *   nodesInfo         — Object map of nodeId → node data (from graphData.nodes_info)
 *   onClose           — callback to deselect
 *   killedNodes       — Set<string> of manually/auto-killed node IDs
 */
export function NodeInspector({ nodeId, nodesInfo, onClose, killedNodes }) {
  const node = nodesInfo[nodeId];
  if (!node) return null;

  const appState = node.appState || {};
  const isKilled = node.isDead || killedNodes.has(nodeId);

  const cpu     = appState.cpu     ?? "—";
  const memory  = appState.memory  ?? "—";
  const network = appState.network ?? "—";
  const storage = appState.storage ?? "—";

  const isCpuFiltered     = appState._isCpuFiltered;
  const isMemoryFiltered  = appState._isMemoryFiltered;
  const isNetworkFiltered = appState._isNetworkFiltered;
  const isStorageFiltered = appState._isStorageFiltered;

  const activeNodeCount = node.active_target || Math.max((node.node_count || 1) - killedNodes.size, 1);
  const isConverged     = node.ic >= activeNodeCount && node.ic > 0;
  const isGossiping     = node.ic > 0 && !isConverged;

  const statusLabel = isKilled ? "TERMINATED" : isConverged ? "Converged" : isGossiping ? "Gossiping" : "Idle";
  const statusStyle = isKilled
    ? { text: "text-red-400",    bg: "bg-red-500/10",     border: "border-red-500/25",     dot: "bg-red-500"     }
    : isConverged
      ? { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25", dot: "bg-emerald-400" }
      : isGossiping
        ? { text: "text-indigo-400",  bg: "bg-indigo-500/10",  border: "border-indigo-500/25",  dot: "bg-indigo-400 animate-pulse"  }
        : { text: "text-slate-400",   bg: "bg-slate-700/30",   border: "border-slate-600/30",   dot: "bg-slate-500"   };

  const nodeTotal    = node.totalMessages || 1;
  const nodeFiltered = node.filteredMessages || 0;
  const nodeSavings  = (nodeFiltered / nodeTotal) * 100;
  const convergePct  = Math.min(100, (node.ic ?? 0) / activeNodeCount * 100);

  const icons = {
    cpu: "M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z",
    mem: "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10",
    net: "M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4",
    disk: "M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4",
  };

  const mkIcon = (d) => (
    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );

  const anyFiltered = isCpuFiltered || isMemoryFiltered || isNetworkFiltered || isStorageFiltered;

  return (
    <div
      className="fixed top-0 right-0 h-full w-80 z-40 flex flex-col slide-in-right"
      style={{
        background: "rgba(7, 11, 20, 0.94)",
        backdropFilter: "blur(28px)",
        WebkitBackdropFilter: "blur(28px)",
        borderLeft: "1px solid rgba(255, 255, 255, 0.06)",
        boxShadow: "-32px 0 80px rgba(0,0,0,0.9)",
      }}
    >
      {/* ── Header ────────────────────────────────────────────────────────────── */}
      <div className="px-5 pt-6 pb-5 border-b border-white/5 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 mb-3">
            <div className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`} />
            <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em]">
              {isKilled ? "Chaos Log" : "Node Inspector"}
            </p>
          </div>

          {/* Node ID */}
          <p className="text-base font-mono font-bold text-white break-all leading-snug">{nodeId}</p>

          {/* Status + savings */}
          <div className="flex flex-wrap items-center gap-2 mt-3">
            <span className={`inline-flex items-center gap-1.5 text-[9px] font-black px-2.5 py-1 rounded-lg border uppercase tracking-wider ${statusStyle.text} ${statusStyle.bg} ${statusStyle.border}`}>
              {statusLabel}
            </span>
            <div className="flex items-center gap-1.5 bg-emerald-500/8 px-2.5 py-1 rounded-lg border border-emerald-500/15">
              <svg className="w-2.5 h-2.5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span className="text-[9px] font-mono font-black text-emerald-400">{nodeSavings.toFixed(0)}% saved</span>
            </div>
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          className="mt-0.5 w-8 h-8 rounded-xl flex items-center justify-center text-slate-600 hover:text-white hover:bg-white/8 transition-all border border-transparent hover:border-white/10 active:scale-90"
          aria-label="Close node inspector"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* ── Body ──────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-5 space-y-6">

        {/* Resources */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-[9px] font-black text-slate-500 uppercase tracking-[0.25em]">System Resources</h4>
            {anyFiltered && (
              <span className="text-[9px] text-amber-500/80 font-bold flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-amber-500 animate-pulse" />
                VoI Active
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            <ResourceCard label="CPU"      value={cpu}     unit="%" isFiltered={isCpuFiltered}     icon={mkIcon(icons.cpu)}  />
            <ResourceCard label="Memory"   value={memory}  unit="%" isFiltered={isMemoryFiltered}  icon={mkIcon(icons.mem)}  />
            <ResourceCard label="Network"  value={network} unit="Mbps" isFiltered={isNetworkFiltered} icon={mkIcon(icons.net)}  />
            <ResourceCard label="Storage"  value={storage} unit="%" isFiltered={isStorageFiltered} icon={mkIcon(icons.disk)} />
          </div>
        </section>

        {/* Convergence */}
        <section className="bg-slate-900/50 rounded-2xl p-4 border border-white/5 space-y-4">
          <h4 className="text-[9px] font-black text-indigo-400 uppercase tracking-[0.25em]">Gossip Convergence</h4>

          {/* Progress */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-[10px] text-slate-500">Progress</span>
              <span className="text-[10px] font-mono font-bold text-white">{Math.min(node.ic ?? 0, activeNodeCount)} / {activeNodeCount}</span>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full bar-animate transition-all duration-500 ${isConverged ? "bg-emerald-500" : "bg-indigo-500"}`}
                style={{ width: `${convergePct}%` }}
              />
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Round",     value: node.round ?? 0 },
              { label: "Peers",     value: node.nd ?? 0    },
              { label: "Messages",  value: nodeTotal         },
              { label: "Filtered",  value: nodeFiltered      },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/40 rounded-xl p-3 border border-white/[0.04]">
                <p className="text-[9px] font-bold text-slate-600 uppercase tracking-wider mb-1">{label}</p>
                <p className="text-sm font-mono font-black text-white">{value.toLocaleString()}</p>
              </div>
            ))}
          </div>
        </section>

      </div>

      {/* ── Footer ────────────────────────────────────────────────────────────── */}
      <div className="px-5 py-4 border-t border-white/5 bg-black/20">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-mono text-slate-700">PORT: {nodeId.split(":").pop()}</span>
          <div className="flex items-center gap-1.5">
            <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[9px] font-mono text-emerald-700 font-bold">LIVE</span>
          </div>
        </div>
      </div>
    </div>
  );
}
