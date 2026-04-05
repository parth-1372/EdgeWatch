import React, { useRef, useEffect, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";

/**
 * LiveTopologyGraph — renders the force-directed network graph and the
 * Live Diagnostic Feed table below it.
 *
 * Props:
 *   graphData      — { nodes, links, nodes_info }
 *   onSelectNode   — callback(nodeId) to open the inspector panel
 *   killedNodes    — Set<string> of dead node IDs
 *   onKillNode     — callback(nodeId) to trigger Chaos Engine kill
 *   selectedNodeId — currently selected node ID or null
 */
export function LiveTopologyGraph({ graphData, onSelectNode, killedNodes, pendingKills, onKillNode, selectedNodeId }) {
  const graphRef = useRef();

  // Auto-fit the graph whenever the node count changes
  useEffect(() => {
    let timerId = null;
    if (graphRef.current && graphData.nodes.length > 0) {
      const fg = graphRef.current;
      const centerForce = fg.d3Force("center");
      if (centerForce) centerForce.x(0).y(0);

      timerId = setTimeout(() => {
        fg.zoomToFit(400, 100);
      }, 150);
    }
    return () => {
      if (timerId) clearTimeout(timerId);
    };
  }, [graphData.nodes.length]);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const isKilled   = killedNodes.has(node.id);
    const isSelected = selectedNodeId === node.id;
    const isPending  = pendingKills?.has(node.id);
    const r          = isSelected ? 11 : 8;
    const { ic, node_count } = node;
    const activeNodeCount = node.active_target || Math.max((node_count || 1) - killedNodes.size, 1);

    let color = "#64748b";
    if (isKilled)       color = "#475569";
    else if (isPending) color = "#f59e0b";
    else if (ic > 0)    color = ic >= activeNodeCount ? "#10b981" : "#6366f1";

    // Outer glow ring (selected or converged)
    if (!isKilled) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 6, 0, 2 * Math.PI);
      ctx.fillStyle = isSelected ? `${color}30` : `${color}15`;
      ctx.fill();
    }

    // Node disc
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = isKilled ? "transparent" : color;
    ctx.fill();

    // Border
    ctx.strokeStyle = isKilled ? "#ef444440" : isSelected ? "#fff" : `${color}80`;
    ctx.lineWidth   = isKilled ? 1.5 : isSelected ? 2.5 : 1.5;
    ctx.setLineDash(isKilled ? [3, 2] : []);
    ctx.stroke();
    ctx.setLineDash([]);

    // Label
    const labelSize = Math.max(9 / globalScale, 3);
    ctx.font         = `${isKilled ? "italic " : "600 "}${labelSize}px Inter, sans-serif`;
    ctx.textAlign    = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle    = isKilled ? "#475569" : isSelected ? "#fff" : "rgba(203, 213, 225, 0.9)";
    ctx.fillText(node.label || node.id, node.x, node.y + r + 4);

    // Killed ✕
    if (isKilled) {
      ctx.font      = `bold ${labelSize * 0.9}px monospace`;
      ctx.fillStyle = "#ef4444";
      ctx.fillText("✕", node.x, node.y - r * 0.5);
    }

    // Pending kill indicator
    if (isPending && !isKilled) {
      ctx.font      = `bold ${labelSize * 0.9}px monospace`;
      ctx.fillStyle = "#f59e0b";
      ctx.fillText("⚡", node.x, node.y - r * 0.5);
    }
  }, [killedNodes, selectedNodeId, pendingKills]);

  const nodeCount   = graphData.nodes.length;
  const linkCount   = graphData.links.length;
  const aliveCount  = nodeCount - killedNodes.size;

  return (
    <div className="glass rounded-3xl border border-white/6 overflow-hidden shadow-2xl">

      {/* Graph header */}
      <div className="px-6 py-4 flex items-center justify-between border-b border-white/5 bg-gradient-to-r from-slate-900/60 to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
            </svg>
          </div>
          <div>
            <h2 className="text-white font-bold text-sm tracking-tight">Network Topology</h2>
            <p className="text-[10px] text-slate-500 font-medium">Live force-directed cluster graph</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[
            { label: "Nodes",  value: nodeCount,  color: "text-indigo-400" },
            { label: "Active", value: aliveCount,  color: "text-emerald-400" },
            { label: "Links",  value: linkCount,  color: "text-cyan-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass px-3 py-1.5 rounded-lg text-center min-w-[60px]">
              <p className={`text-sm font-mono font-black ${color}`}>{value}</p>
              <p className="text-[9px] text-slate-600 font-medium uppercase tracking-wider">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Force graph canvas */}
      <div
        className="relative"
        style={{ height: 480, background: "radial-gradient(ellipse at 50% 50%, #0d1b2e 0%, #020617 70%)" }}
      >
        {nodeCount === 0 ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <svg className="w-10 h-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
            </svg>
            <p className="text-slate-600 font-mono text-xs animate-pulse">Awaiting orchestrator data stream...</p>
            <p className="text-slate-700 text-[10px]">Boot the network to begin</p>
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeCanvasObject={paintNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.beginPath();
              ctx.arc(node.x, node.y, 14, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            onNodeClick={node => onSelectNode(node.id)}
            linkColor={link =>
              killedNodes.has(link.source.id) || killedNodes.has(link.target.id)
                ? "rgba(239, 68, 68, 0.04)"
                : "rgba(99, 102, 241, 0.15)"
            }
            linkWidth={1.5}
            linkDirectionalParticles={2}
            linkDirectionalParticleWidth={2.5}
            linkDirectionalParticleColor={() => "rgba(99, 102, 241, 0.5)"}
            backgroundColor="transparent"
            height={480}
            cooldownTicks={100}
            d3AlphaDecay={0.01}
            d3VelocityDecay={0.3}
          />
        )}
      </div>

      {/* Legend bar */}
      <div className="px-6 py-3 border-t border-white/5 bg-slate-950/30 flex items-center gap-6">
        {[
          { color: "bg-emerald-500",  label: "Converged"  },
          { color: "bg-indigo-500",   label: "Gossiping"  },
          { color: "bg-amber-500",    label: "Pending Kill" },
          { color: "bg-red-500/40 border border-red-500/40", label: "Terminated" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
            <span className="text-[10px] text-slate-500 font-medium">{label}</span>
          </div>
        ))}
        <div className="ml-auto text-[10px] text-slate-700 font-mono">Click a node to inspect</div>
      </div>

      {/* Diagnostic table */}
      <div className="border-t border-white/5">
        <div className="px-6 py-3 flex items-center justify-between bg-slate-900/40 border-b border-white/5">
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Live Diagnostic Feed</h3>
          <span className="text-[10px] font-mono text-slate-700">{Object.keys(graphData.nodes_info || {}).length} nodes tracked</span>
        </div>
        <div className="max-h-[320px] overflow-y-auto custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-md text-[9px] text-slate-600 uppercase font-black border-b border-white/5">
              <tr>
                <th className="px-6 py-3 tracking-widest">Node Endpoint</th>
                <th className="px-4 py-3 tracking-widest">Round</th>
                <th className="px-4 py-3 tracking-widest">Peers</th>
                <th className="px-4 py-3 tracking-widest">Data</th>
                <th className="px-4 py-3 tracking-widest">Health</th>
                <th className="px-4 py-3 tracking-widest">Convergence</th>
                <th className="px-4 py-3 tracking-widest text-right pr-6">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {Object.values(graphData.nodes_info || {})
                .sort((a, b) => b.lastSeen - a.lastSeen)
                .map(node => {
                  const isKilled       = killedNodes.has(node.id);
                  const activeNodeCount = node.active_target || Math.max((node.node_count || 1) - killedNodes.size, 1);
                  const isConverged    = node.ic >= activeNodeCount && node.ic > 0;
                  const isPending      = pendingKills?.has(node.id);

                  return (
                    <tr
                      key={node.id}
                      className={`group transition-all duration-150 cursor-pointer ${
                        isKilled ? "opacity-40" : "hover:bg-white/[0.025]"
                      } ${selectedNodeId === node.id ? "bg-indigo-500/5" : ""}`}
                      onClick={() => onSelectNode(node.id)}
                    >
                      <td className="px-6 py-3.5 whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          <div className={`w-2 h-2 rounded-full shrink-0 ${
                            isKilled ? "bg-red-500/60" : isConverged ? "bg-emerald-500" : isPending ? "bg-amber-500 animate-pulse" : "bg-indigo-500 animate-pulse"
                          }`} />
                          <span className="text-slate-300 font-mono text-[11px] group-hover:text-white transition-colors">{node.id}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">{node.round ?? 0}</td>
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">{node.nd ?? 0}</td>
                      <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">{((node.bytes_of_data || 0) / 1024).toFixed(1)} KB</td>
                      <td className="px-4 py-3.5">
                        {(node.strikes || 0) > 0 ? (
                          <span className={`text-[9px] font-mono font-black px-2 py-0.5 rounded-md ${
                            node.strikes >= 3
                              ? "text-red-400 bg-red-500/10 border border-red-500/20"
                              : "text-amber-400 bg-amber-500/10 border border-amber-500/20 animate-pulse"
                          }`}>
                            {node.strikes >= 3 ? "DEAD" : `${node.strikes}/3 ⚠`}
                          </span>
                        ) : (
                          <span className="text-[9px] font-mono font-black text-emerald-500/70">HEALTHY</span>
                        )}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-14 h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${isConverged ? "bg-emerald-500" : "bg-indigo-500"}`}
                              style={{ width: `${Math.min(100, (node.ic / activeNodeCount) * 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-slate-600 font-mono">{node.ic}/{activeNodeCount}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-right pr-6" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => onKillNode(node.id)}
                          disabled={isKilled || isPending}
                          className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all duration-200 ${
                            isKilled
                              ? "bg-red-500/5 text-red-900 border border-red-900/10 cursor-default"
                              : isPending
                                ? "bg-amber-500/10 text-amber-500/60 border border-amber-500/20 cursor-wait"
                                : "bg-red-500/8 text-red-500 border border-red-500/15 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/40 active:scale-95"
                          }`}
                        >
                          {isKilled ? "Dead" : isPending ? "Killing..." : "Kill"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
          {Object.keys(graphData.nodes_info || {}).length === 0 && (
            <div className="py-12 flex items-center justify-center">
              <p className="text-slate-700 font-mono text-xs">No nodes detected yet</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
