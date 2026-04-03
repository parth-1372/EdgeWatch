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
    const r          = isSelected ? 10 : 8;
    const { ic, node_count } = node;
    const activeNodeCount = node.active_target || Math.max((node_count || 1) - killedNodes.size, 1);

    let color = "#64748b";
    if (isKilled) {
      color = "#475569";
    } else if (ic > 0) {
      color = ic >= activeNodeCount ? "#10b981" : "#6366f1";
    }

    // Glow halo
    ctx.beginPath();
    ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI);
    ctx.fillStyle = isKilled ? "transparent" : `${color}22`;
    ctx.fill();

    // Main node disc
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = isKilled ? "transparent" : color;
    ctx.fill();

    // Border
    ctx.strokeStyle = isKilled ? "#ef444466" : isSelected ? "#fff" : "rgba(255,255,255,0.3)";
    ctx.lineWidth   = isKilled ? 2 : isSelected ? 3 : 1;
    ctx.setLineDash(isKilled ? [2, 1] : []);
    ctx.stroke();
    ctx.setLineDash([]);

    // Label
    const labelSize = Math.max(10 / globalScale, 3);
    ctx.font         = `${isKilled ? "italic " : ""}${labelSize}px "JetBrains Mono", Inter, sans-serif`;
    ctx.textAlign    = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle    = isKilled ? "#64748b" : isSelected ? "#fff" : "rgba(226, 232, 240, 0.9)";
    ctx.fillText(node.label || node.id, node.x, node.y + r + 3);

    // Killed ✕ marker
    if (isKilled) {
      ctx.font      = `${labelSize * 0.8}px monospace`;
      ctx.fillStyle = "#ef4444";
      ctx.fillText("✕", node.x, node.y - r / 1.5);
    }
  }, [killedNodes, selectedNodeId]);

  const nodeCount = graphData.nodes.length;
  const linkCount = graphData.links.length;

  return (
    <div className="rounded-3xl bg-slate-800/40 border border-slate-700/50 backdrop-blur-md overflow-hidden shadow-2xl">
      {/* Graph header */}
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

      {/* Force graph canvas */}
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
            onNodeClick={node => onSelectNode(node.id)}
            linkColor={link =>
              killedNodes.has(link.source.id) || killedNodes.has(link.target.id)
                ? "rgba(239, 68, 68, 0.05)"
                : "rgba(56, 189, 248, 0.1)"
            }
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

      {/* Diagnostic table */}
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
                <th className="px-4 py-4 font-black">Health</th>
                <th className="px-4 py-4 font-black">Convergence</th>
                <th className="px-4 py-4 font-black text-right pr-8">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {Object.values(graphData.nodes_info || {})
                .sort((a, b) => b.lastSeen - a.lastSeen)
                .map(node => {
                  const isKilled       = killedNodes.has(node.id);
                  const activeNodeCount = node.active_target || Math.max((node.node_count || 1) - killedNodes.size, 1);
                  const isConverged    = node.ic >= activeNodeCount && node.ic > 0;

                  return (
                    <tr
                      key={node.id}
                      className={`group transition-all hover:bg-white/5 cursor-pointer ${isKilled ? "opacity-40 grayscale" : ""}`}
                      onClick={() => onSelectNode(node.id)}
                    >
                      <td className="px-8 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${isKilled ? "bg-red-500" : isConverged ? "bg-emerald-500" : "bg-indigo-500"}`} />
                          <span className="text-slate-200 font-mono text-xs group-hover:text-white">{node.id}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 font-mono text-xs text-slate-400">{node.round}</td>
                      <td className="px-4 py-4 font-mono text-xs text-slate-400">{node.nd}</td>
                      <td className="px-4 py-4 font-mono text-xs text-slate-400">{((node.bytes_of_data || 0) / 1024).toFixed(1)} KB</td>
                      <td className="px-4 py-4">
                        {(node.strikes || 0) > 0 ? (
                          <span className={`text-[10px] font-mono font-bold px-2 py-1 rounded ${node.strikes >= 3 ? "text-red-500 bg-red-500/10" : "text-amber-500 bg-amber-500/10 animate-pulse"}`}>
                            {node.strikes >= 3 ? "AMPUTATED" : `STRIKES: ${node.strikes}/3`}
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono font-bold text-emerald-500/80">HEALTHY</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-1 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${isConverged ? "bg-emerald-500" : "bg-indigo-500"}`}
                              style={{ width: `${Math.min(100, (node.ic / activeNodeCount) * 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">{node.ic}/{activeNodeCount}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-right pr-8" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => onKillNode(node.id)}
                          disabled={isKilled || pendingKills.has(node.id)}
                          className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${
                            isKilled
                              ? "bg-red-500/10 text-red-700 border border-red-900/20"
                              : pendingKills.has(node.id)
                                ? "bg-amber-500/10 text-amber-500/50 border border-amber-500/20 cursor-wait"
                                : "bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/30 hover:text-red-100 hover:border-red-500/50 active:scale-95"
                          }`}
                        >
                          {isKilled ? "Terminated" : pendingKills.has(node.id) ? "Killing..." : "Kill Node"}
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
