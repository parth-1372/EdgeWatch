import React from "react";
import { useState, useEffect, useCallback, useRef, useMemo } from "react";
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

/** Extract only the IP from "ip:port" string */
function ipOnly(nodeId) {
  return nodeId ? nodeId.split(":")[0] : nodeId;
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
// VoI Efficiency Badge — shown in header
// ---------------------------------------------------------------------------
function GlobalEfficiencyBadge({ savingsPercent }) {
  return (
    <div className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg shadow-inner cursor-help" title="Percentage of redundant network updates successfully filtered by the Value-of-Information logic.">
      <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">VoI Efficiency</span>
      <span className="text-sm font-mono font-bold text-emerald-300">{savingsPercent.toFixed(1)}%</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SectionCard — renders one INI section with editable inputs (v1.2 styling)
// ---------------------------------------------------------------------------
function SectionCard({ sectionKey, sectionData, onChange }) {
  const sectionMeta = {
    PriomonParam: { accent: "from-violet-500/20 to-indigo-600/20", border: "border-violet-500/30", text: "text-violet-400" },
    system_setting: { accent: "from-cyan-500/20 to-sky-600/20", border: "border-cyan-500/30", text: "text-cyan-400" },
    database: { accent: "from-amber-500/20 to-orange-600/20", border: "border-amber-500/30", text: "text-amber-400" },
  };

  const meta = sectionMeta[sectionKey] || {
    accent: "from-slate-500/20 to-slate-700/20",
    border: "border-slate-500/30",
    text: "text-slate-400",
  };

  return (
    <div className={`col-span-1 rounded-3xl bg-slate-900/40 border ${meta.border} backdrop-blur-md overflow-hidden transition-all hover:bg-slate-900/60 flex flex-col h-full`}>
      <div className={`bg-gradient-to-r ${meta.accent} px-6 py-4 border-b ${meta.border} flex items-center gap-3 shrink-0`}>
        <div className="w-1.5 h-1.5 rounded-full bg-white opacity-50 shadow-[0_0_8px_rgba(255,255,255,0.4)]" />
        <h2 className={`text-[10px] font-black uppercase tracking-[0.3em] ${meta.text}`}>
          [{sectionKey}]
        </h2>
      </div>

      <div className="p-6 grid grid-cols-1 gap-y-5 overflow-y-auto flex-1 custom-scrollbar">
        {Object.entries(sectionData).map(([key, value]) => {
          if (key.startsWith(";")) return null;

          const inputId = `${sectionKey}__${key}`;
          const strVal = value === null || value === undefined ? "" : String(value);

          return (
            <div key={key} className="flex flex-col gap-2">
              <label htmlFor={inputId} className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">
                {sectionLabel(key)}
              </label>
              <input
                id={inputId}
                type="text"
                value={strVal}
                onChange={(e) => onChange(sectionKey, key, e.target.value)}
                className="
                  bg-black/40 border border-white/5 rounded-xl px-4 py-2.5
                  text-slate-100 text-xs font-mono placeholder-slate-700
                  focus:outline-none focus:ring-1 focus:ring-white/20 focus:border-white/20
                  transition-all duration-200
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
// ResourceCard — used in Node Inspector 2x2 grid
// ---------------------------------------------------------------------------
function ResourceCard({ label, value, unit = "", icon, isFiltered }) {
  let displayValue = value;
  if (isNumeric(value)) {
    displayValue = parseFloat(value).toFixed(2);
  }

  return (
    <div className="relative bg-slate-900/50 border border-slate-700/50 rounded-xl p-3 flex flex-col gap-1 overflow-hidden transition-all hover:bg-slate-900/80">
      {isFiltered && (
        <div className="absolute top-1.5 right-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse" title="VoI Filtered (Stale Value)" />
        </div>
      )}
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <span className="text-[9px] font-bold uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1 mt-0.5">
        <span className={`text-lg font-mono font-bold ${isFiltered ? 'text-slate-400' : 'text-white'}`}>
          {displayValue}
        </span>
        <span className="text-[9px] text-slate-600 font-medium">{unit}</span>
      </div>
      <div className="mt-2 w-full h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ${isNumeric(value) ? (value > 80 ? 'bg-red-500' : value > 50 ? 'bg-amber-500' : 'bg-emerald-500') : 'bg-slate-700'}`}
          style={{ width: `${isNumeric(value) ? Math.min(value, 100) : 0}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NodeInspector — floating side-panel overlay for a selected node
// ---------------------------------------------------------------------------
function NodeInspector({ nodeId, nodesInfo, onClose, totalGlobalMessages, totalGlobalFiltered, killedNodes }) {
  const node = nodesInfo[nodeId];

  if (!node) return null;

  const appState = node.appState || {};
  const isKilled = node.isDead || killedNodes.has(nodeId);

  const cpu = appState.cpu ?? "0";
  const memory = appState.memory ?? "0";
  const network = appState.network ?? "0";
  const storage = appState.storage ?? "0";

  const isCpuFiltered = appState._isCpuFiltered;
  const isMemoryFiltered = appState._isMemoryFiltered;
  const isNetworkFiltered = appState._isNetworkFiltered;
  const isStorageFiltered = appState._isStorageFiltered;
  const activeNodeCount = node.active_target || Math.max((node.node_count || 1) - killedNodes.size, 1);
  const isConverged = node.ic >= activeNodeCount && node.ic > 0;
  const isGossiping = node.ic > 0 && !isConverged;
  const statusLabel = isKilled ? "TERMINATED" : isConverged ? "Converged" : isGossiping ? "Gossiping" : "Running";
  const statusColor = isKilled
    ? "text-red-500 bg-red-500/10 border-red-500/30"
    : isConverged
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
      : isGossiping
        ? "text-indigo-400 bg-indigo-500/10 border-indigo-500/20"
        : "text-slate-400 bg-slate-700/30 border-slate-700/50";

  const nodeTotal = node.totalMessages || 1;
  const nodeFiltered = node.filteredMessages || 0;
  const nodeSavings = (nodeFiltered / nodeTotal) * 100;

  return (
    <div
      className={`fixed top-0 right-0 h-full w-85 z-40 flex flex-col transition-transform duration-300 transform ${nodeId ? 'translate-x-0' : 'translate-x-full'}`}
      style={{
        background: "rgba(10, 15, 25, 0.92)",
        backdropFilter: "blur(24px)",
        borderLeft: "1px solid rgba(100, 116, 139, 0.2)",
        boxShadow: "-24px 0 64px rgba(0,0,0,0.8)",
      }}
    >
      <div className="px-6 pt-8 pb-5 border-b border-white/5 flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${isKilled ? 'bg-red-500' : isConverged ? 'bg-emerald-500' : 'bg-indigo-500'} animate-pulse`} />
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.25em]">
              {isKilled ? 'Chaos Event Log' : 'Node Diagnostic'}
            </p>
          </div>
          <p className="text-xl font-mono text-white font-bold break-all leading-tight">
            {nodeId}
          </p>
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
        <button onClick={onClose} className="mt-1 w-8 h-8 rounded-xl flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all border border-transparent hover:border-white/20 active:scale-95">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 custom-scrollbar space-y-8">
        <section>
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-[10px] font-black text-cyan-400 uppercase tracking-[0.2em]">Real-Time Resources</h4>
            {isCpuFiltered || isMemoryFiltered || isNetworkFiltered || isStorageFiltered ? (
              <span className="text-[9px] text-amber-500/80 font-bold flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-amber-500 animate-pulse" /> VoI Active
              </span>
            ) : null}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ResourceCard label="CPU Load" value={cpu} unit="%" isFiltered={isCpuFiltered} icon={<svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>} />
            <ResourceCard label="Memory" value={memory} unit="%" isFiltered={isMemoryFiltered} icon={<svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>} />
            <ResourceCard label="Bandwidth" value={network} unit="Mbps" isFiltered={isNetworkFiltered} icon={<svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" /></svg>} />
            <ResourceCard label="Disk Usage" value={storage} unit="%" isFiltered={isStorageFiltered} icon={<svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" /></svg>} />
          </div>
        </section>

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

      <div className="px-6 py-5 border-t border-white/5 bg-slate-950/50">
        <div className="flex items-center justify-between">
          <span className="text-[9px] font-mono text-slate-600">ID: {nodeId.split(':').pop()}</span>
          <span className="text-[9px] font-mono text-emerald-600 font-bold">LIVE STREAMING</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Live Topology Graph component
// ---------------------------------------------------------------------------
function LiveTopologyGraph({ graphData, metricsLog, onSelectNode, killedNodes, onKillNode, selectedNodeId }) {
  const graphRef = useRef();

  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      const fg = graphRef.current;
      const centerForce = fg.d3Force('center');
      if (centerForce) centerForce.x(0).y(0);
      setTimeout(() => fg.zoomToFit(400, 100), 150);
    }
  }, [graphData.nodes.length]);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const isKilled = killedNodes.has(node.id);
    const isSelected = selectedNodeId === node.id;
    const r = isSelected ? 10 : 8;
    const { ic, node_count } = node;
    const activeNodeCount = Math.max((node_count || 1) - killedNodes.size, 1);

    let color = "#64748b";
    if (isKilled) {
      color = "#475569";
    } else if (ic > 0) {
      color = ic >= activeNodeCount ? "#10b981" : "#6366f1";
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
    ctx.fillStyle = isKilled ? 'transparent' : `${color}22`;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = isKilled ? 'transparent' : color;
    ctx.fill();

    ctx.strokeStyle = isKilled ? '#ef444466' : isSelected ? '#fff' : "rgba(255,255,255,0.3)";
    ctx.lineWidth = isKilled ? 2 : isSelected ? 3 : 1;
    if (isKilled) {
      ctx.setLineDash([2, 1]);
    } else {
      ctx.setLineDash([]);
    }
    ctx.stroke();

    const labelSize = Math.max(10 / globalScale, 3);
    ctx.font = `${isKilled ? 'italic ' : ''}${labelSize}px "JetBrains Mono", Inter, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = isKilled ? "#64748b" : isSelected ? "#fff" : "rgba(226, 232, 240, 0.9)";
    ctx.fillText(node.label || node.id, node.x, node.y + r + 3);

    if (isKilled) {
      ctx.font = `${labelSize * 0.8}px monospace font-black`;
      ctx.fillStyle = "#ef4444";
      ctx.fillText("✕", node.x, node.y - r / 1.5);
    }
  }, [killedNodes, selectedNodeId]);

  const nodeCount = graphData.nodes.length;
  const linkCount = graphData.links.length;

  return (
    <div className="rounded-3xl bg-slate-800/40 border border-slate-700/50 backdrop-blur-md overflow-hidden shadow-2xl">
      <div className="bg-gradient-to-r from-slate-900/80 to-slate-900 px-8 py-5 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="flex -space-x-1">
            <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <div className="w-3 h-3 rounded-full bg-indigo-500/50" />
          </div>
          <h2 className="text-white font-bold text-lg tracking-tight">Network Health Topology</h2>
        </div>
        <div className="flex items-center gap-6 text-slate-400 text-xs font-mono font-medium">
          <div className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
            <span className="text-slate-500 mr-1.5">Nodes:</span>{nodeCount}
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
            <span className="text-slate-500 mr-1.5">Links:</span>{linkCount}
          </div>
        </div>
      </div>

      <div className="relative" style={{ height: 500, background: "radial-gradient(circle at center, #0f172a 0%, #020617 100%)" }}>
        {nodeCount === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-slate-500 font-mono text-sm animate-pulse">Awaiting data stream from orchestrator...</p>
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeCanvasObject={paintNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.beginPath();
              ctx.arc(node.x, node.y, 12, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            onNodeClick={(node) => onSelectNode(node.id)}
            linkColor={(link) => killedNodes.has(link.source.id) || killedNodes.has(link.target.id) ? "rgba(239, 68, 68, 0.05)" : "rgba(56, 189, 248, 0.1)"}
            linkWidth={1.5}
            linkDirectionalParticles={2}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={() => "rgba(56, 189, 248, 0.3)"}
            backgroundColor="#020617"
            height={500}
            cooldownTicks={100}
            d3AlphaDecay={0.01}
            d3VelocityDecay={0.3}
          />
        )}
      </div>

      <div className="border-t border-white/5 bg-slate-950/20">
        <div className="px-8 py-3 bg-slate-900/40 border-b border-white/5">
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Live Diagnostic Feed</h3>
        </div>
        <div className="max-h-[350px] overflow-y-auto custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-md text-[10px] text-slate-500 uppercase font-mono border-b border-white/5">
              <tr>
                <th className="px-8 py-4 font-black">Node Endpoint</th>
                <th className="px-4 py-4 font-black">Round</th>
                <th className="px-4 py-4 font-black">ND</th>
                <th className="px-4 py-4 font-black">Data</th>
                <th className="px-4 py-4 font-black">Efficiency</th>
                <th className="px-4 py-4 font-black">Convergence</th>
                <th className="px-4 py-4 font-black text-right pr-8">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {Object.values(graphData.nodes_info || {}).sort((a, b) => b.lastSeen - a.lastSeen).map((node) => {
                const isKilled = killedNodes.has(node.id);
                const activeNodeCount = Math.max((node.node_count || 1) - killedNodes.size, 1);
                const isConverged = node.ic >= activeNodeCount && node.ic > 0;

                const savings = ((node.filteredMessages || 0) / (node.totalMessages || 1)) * 100;

                return (
                  <tr
                    key={node.id}
                    className={`group transition-all hover:bg-white/5 cursor-pointer ${isKilled ? 'opacity-40 grayscale' : ''}`}
                    onClick={() => onSelectNode(node.id)}
                  >
                    <td className="px-8 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${isKilled ? 'bg-red-500 flex items-center justify-center text-[6px] text-white' : isConverged ? 'bg-emerald-500' : 'bg-indigo-500'}`}>
                          {isKilled && "✕"}
                        </div>
                        <span className="text-slate-200 font-mono text-xs group-hover:text-white">{node.id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 font-mono text-xs text-slate-400">{node.round}</td>
                    <td className="px-4 py-4 font-mono text-xs text-slate-400">{node.nd}</td>
                    <td className="px-4 py-4 font-mono text-xs text-slate-400">{(node.bytes_of_data / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-4">
                      {node.strikes > 0 ? (
                        <span className={`text-[10px] font-mono font-bold px-2 py-1 rounded ${node.strikes >= 3 ? 'text-red-500 bg-red-500/10' : 'text-amber-500 bg-amber-500/10 animate-pulse'}`}>
                          {node.strikes >= 3 ? 'AMPUTATED' : `STRIKES: ${node.strikes}/3`}
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono font-bold text-emerald-500/80">HEALTHY</span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-1 bg-slate-800 rounded-full overflow-hidden">
                          <div className={`h-full ${isConverged ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${(node.ic / activeNodeCount) * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-slate-500 font-mono">{node.ic}/{activeNodeCount}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-right pr-8" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => onKillNode(node.id)}
                        disabled={isKilled}
                        className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${isKilled ? 'bg-red-500/10 text-red-700 border border-red-900/20' : 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/30 hover:text-red-100 hover:border-red-500/50 active:scale-95'}`}
                      >
                        {isKilled ? 'Terminated' : 'Kill Node'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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

  const [graphData, setGraphData] = useState({ nodes: [], links: [], nodes_info: {} });
  const [metricsLog, setMetricsLog] = useState([]);
  const nodesMapRef = useRef(new Map());
  const linksSetRef = useRef(new Set());
  const strikesMapRef = useRef(new Map());

  // Global VoI Stats
  const [globalTotalMessages, setGlobalTotalMessages] = useState(0);
  const [globalFilteredMessages, setGlobalFilteredMessages] = useState(0);

  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [killedNodes, setKilledNodes] = useState(new Set());

  const globalSavingsPercent = useMemo(() => {
    if (globalTotalMessages === 0) return 0;
    return (globalFilteredMessages / globalTotalMessages) * 100;
  }, [globalTotalMessages, globalFilteredMessages]);

  const handleKillNode = useCallback(async (nodeId) => {
    const ip = ipOnly(nodeId);
    const port = nodeId.includes(":") ? nodeId.split(":")[1] : "";
    try {
      const res = await fetch(`${API_BASE}/kill-node/${ip}/${port}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);

      setKilledNodes((prev) => new Set([...prev, nodeId]));

      // Mark it dead in the internal state immediately so graph renders it
      const map = nodesMapRef.current;
      if (map.has(nodeId)) {
        map.get(nodeId).isDead = true;
      }

      setToast({ message: `⚡ Node ${ip} terminated. Gossip peers will detect failure within 3 rounds.`, type: "success" });
    } catch (err) {
      setToast({ message: `${err.message}`, type: "error" });
    }
  }, []);

  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ["websocket"] });

    socket.on("run_started", (p) => {
      nodesMapRef.current = new Map();
      linksSetRef.current = new Set();
      strikesMapRef.current = new Map();
      setKilledNodes(new Set());
      setGlobalTotalMessages(0);
      setGlobalFilteredMessages(0);
      setSelectedNodeId(null);

      const now = Date.now();
      const nodeCount = p.node_count || 1;
      p.nodes.forEach(n => {
        const id = `${n.ip}:${n.port}`;
        nodesMapRef.current.set(id, {
          id, label: id, ic: 0, node_count: nodeCount, round: 0, nd: 0, rm: 0,
          bytes_of_data: 0, lastSeen: now, x: (Math.random() - 0.5) * 50, y: (Math.random() - 0.5) * 50,
          totalMessages: 0, filteredMessages: 0, appState: {}, isDead: false
        });
      });
      setGraphData({
        nodes: Array.from(nodesMapRef.current.values()),
        links: [],
        nodes_info: Object.fromEntries(nodesMapRef.current)
      });
    });

    socket.on("new_metric", (p) => {
      const senderKey = `${p.ip}:${p.port}`;
      const now = Date.now();
      const nodesMap = nodesMapRef.current;
      const linksSet = linksSetRef.current;

      setMetricsLog(prev => {
        const next = [...prev, p];
        return next.length > 50 ? next.slice(-50) : next;
      });

      let node = nodesMap.get(senderKey);
      if (!node) {
        node = { id: senderKey, label: senderKey, x: (Math.random() - 0.5) * 50, y: (Math.random() - 0.5) * 50, isDead: false };
        nodesMap.set(senderKey, node);
      }

      // Track VoI Savings Logic
      let isMetricsFiltered = false;
      const fields = ['cpu', 'memory', 'network', 'storage'];
      const fieldStats = {};

      fields.forEach(f => {
        const val = p[f];
        if (val === "not_updated") {
          isMetricsFiltered = true;
          fieldStats[f] = node.appState?.[f] && node.appState[f] !== "not_updated" ? node.appState[f] : "not_updated";
        } else if (val !== undefined) {
          fieldStats[f] = val;
        }
      });

      setGlobalTotalMessages(v => v + 1);
      if (isMetricsFiltered) setGlobalFilteredMessages(v => v + 1);

      Object.assign(node, {
        ic: p.ic || 0,
        node_count: p.node_count || 1,
        active_target: p.active_target || p.node_count || 1,
        round: p.round || 0,
        nd: p.nd || 0,
        rm: p.rm || 0,
        bytes_of_data: p.bytes_of_data || 0,
        lastSeen: now,
        totalMessages: (node.totalMessages || 0) + 1,
        filteredMessages: (node.filteredMessages || 0) + (isMetricsFiltered ? 1 : 0),
        appState: {
          ...(node.appState || {}),
          ...fieldStats,
          cpu: p.cpu === "not_updated" ? (node.appState?.cpu ?? "not_updated") : p.cpu,
          memory: p.memory === "not_updated" ? (node.appState?.memory ?? "not_updated") : p.memory,
          network: p.network === "not_updated" ? (node.appState?.network ?? "not_updated") : p.network,
          storage: p.storage === "not_updated" ? (node.appState?.storage ?? "not_updated") : p.storage,
          _isCpuFiltered: p.cpu === "not_updated",
          _isMemoryFiltered: p.memory === "not_updated",
          _isNetworkFiltered: p.network === "not_updated",
          _isStorageFiltered: p.storage === "not_updated"
        }
      });

      const peers = p.data_stored_in_node || [];
      const peerStatus = p.peer_status || {};

      peers.forEach(peerKey => {
        if (typeof peerKey !== "string" || peerKey === senderKey) return;

        let targetDead = false;
        if (peerStatus[peerKey]) {
          const stats = peerStatus[peerKey];

          // Track the highest strike count globally across all nodes
          if (stats.failCount > 0) {
            const currentStrikes = strikesMapRef.current.get(peerKey) || 0;
            strikesMapRef.current.set(peerKey, Math.max(currentStrikes, stats.failCount));
          }

          if (stats.failCount > 0) {
            if (!node.appState._failCounts) node.appState._failCounts = {};
            node.appState._failCounts[peerKey] = stats.failCount;
          }
          if (stats.isAlive === false || stats.failCount >= 3) {
            targetDead = true;
          }
        }

        if (!nodesMap.has(peerKey)) {
          nodesMap.set(peerKey, {
            id: peerKey, label: peerKey, ic: 0, node_count: p.node_count || 1,
            round: 0, nd: 0, rm: 0, bytes_of_data: 0, lastSeen: now,
            x: (Math.random() - 0.5) * 100, y: (Math.random() - 0.5) * 100, appState: {}, isDead: false
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

      // Pass strikes to UI and kill nodes that reach 3 strikes
      Array.from(nodesMap.values()).forEach(n => {
        n.strikes = strikesMapRef.current.get(n.id) || 0;
        if (n.strikes >= 3) setKilledNodes(prev => new Set(prev).add(n.id));
      });

      // AGGRESSIVELY sever any link touching a node with 3+ strikes OR one that we manually killed
      const validLinks = Array.from(linksSet).map(k => {
        const [source, target] = k.split('->');
        return { source, target };
      }).filter(link => {
        const sStrikes = strikesMapRef.current.get(link.source) || 0;
        const tStrikes = strikesMapRef.current.get(link.target) || 0;
        // severed if either node is marked as killed OR has too many strikes
        const isSourceKilled = killedNodes.has(link.source) || (nodesMap.get(link.source)?.isDead);
        const isTargetKilled = killedNodes.has(link.target) || (nodesMap.get(link.target)?.isDead);
        
        return !isSourceKilled && !isTargetKilled && sStrikes < 3 && tStrikes < 3;
      });

      setGraphData({
        nodes: Array.from(nodesMap.values()),
        links: validLinks,
        nodes_info: Object.fromEntries(nodesMap)
      });
    });

    return () => socket.disconnect();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/config`);
        const data = await res.json();
        setConfig(data);
      } catch (err) { setFetchError(err.message); }
      finally { setLoading(false); }
    })();
  }, []);

  const handleChange = (s, k, v) => setConfig(prev => ({ ...prev, [s]: { ...prev[s], [k]: v } }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      });
      if (!res.ok) throw new Error("Save error");
      setToast({ message: "Configuration cached.", type: "success" });
    } catch (err) { setToast({ message: err.message, type: "error" }); }
    finally { setSaving(false); }
  };

  const handleStart = async () => {
    setBooting(true);
    try {
      const res = await fetch(`${API_BASE}/start`, { method: "POST" });
      if (!res.ok) throw new Error("Orchestrator unreachable");
      setToast({ message: "Live experiment launched.", type: "success" });
    } catch (err) { setToast({ message: err.message, type: "error" }); }
    finally { setBooting(false); }
  };

  if (loading) return <div className="min-h-screen bg-slate-950 flex items-center justify-center font-mono text-slate-500">Initializing Control Center...</div>;

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 selection:bg-violet-500/30 overflow-x-hidden">
      {/* Background Decor */}
      <div className="fixed inset-0 pointer-events-none opacity-30 overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-indigo-600/20 rounded-full blur-[120px] -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-emerald-600/10 rounded-full blur-[120px] translate-y-1/2 -translate-x-1/2" />
      </div>

      <div className="relative max-w-6xl mx-auto px-8 py-12 flex flex-col min-h-[calc(100vh-6rem)]">
        {/* Header Section */}
        <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6 shrink-0">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-600 flex items-center justify-center shadow-xl shadow-indigo-500/20">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              </div>
              <h1 className="text-3xl font-black tracking-tighter text-white">PRIOMON <span className="text-indigo-500">v1.2</span></h1>
            </div>
            <p className="text-slate-500 max-w-md text-sm leading-relaxed font-medium">Distributed Monitoring Control Center with Value-of-Information (VoI) prioritized gossip.</p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <GlobalEfficiencyBadge savingsPercent={globalSavingsPercent} />
            <div className="bg-slate-900 px-4 py-2 rounded-xl border border-white/5 flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none">Stream Status: <span className="text-slate-100">Active</span></span>
            </div>
          </div>
        </header>

        {/* Experiment Actions */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-12 shrink-0">
          <button
            onClick={handleSave}
            disabled={saving || booting}
            className="w-full sm:w-auto px-8 py-4 rounded-2xl bg-slate-900 border border-white/10 hover:bg-slate-800 text-white font-bold text-sm transition-all shadow-lg active:scale-95 disabled:opacity-50"
          >
            {saving ? 'Syncing...' : 'Save Config'}
          </button>
          <button
            onClick={handleStart}
            disabled={booting}
            className="flex-1 px-8 py-4 rounded-2xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-black text-sm tracking-wider shadow-2xl shadow-indigo-600/30 transition-all active:scale-95 disabled:opacity-50"
          >
            {booting ? 'Provisioning...' : 'BOOT DISTRIBUTED NETWORK'}
          </button>
        </div>

        {/* Config Summary - 3 Columns Editable */}
        <section className="space-y-6 mb-12 shrink-0">
          {Object.entries(config).map(([sk, sd]) => (
            <SectionCard key={sk} sectionKey={sk} sectionData={sd} onChange={handleChange} />
          ))}
        </section>

        {/* Network & Diagnostics */}
        <section className="relative flex-1">
          <LiveTopologyGraph
            graphData={graphData}
            metricsLog={metricsLog}
            onSelectNode={setSelectedNodeId}
            killedNodes={killedNodes}
            onKillNode={handleKillNode}
            selectedNodeId={selectedNodeId}
          />
        </section>

        {/* Node Inspector Sidebar */}
        <NodeInspector
          nodeId={selectedNodeId}
          nodesInfo={graphData.nodes_info}
          onClose={() => setSelectedNodeId(null)}
          totalGlobalMessages={globalTotalMessages}
          totalGlobalFiltered={globalFilteredMessages}
          killedNodes={killedNodes}
        />

        {/* Footer */}
        <footer className="mt-20 text-center shrink-0">
          <p className="text-[10px] font-mono text-slate-700 uppercase tracking-[0.4em]">EdgeWatch Project &copy; 2026 · PrioMon Research</p>
        </footer>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onDismiss={() => setToast(null)} />}
    </div>
  );
}
