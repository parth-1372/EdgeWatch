import React from "react";

/** Loading spinner — animated SVG ring. */
export function Spinner() {
  return (
    <div className="relative w-8 h-8">
      <svg className="animate-spin w-8 h-8 text-indigo-500/30" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      </svg>
      <svg className="animate-spin w-8 h-8 text-indigo-400 absolute inset-0" style={{ animationDuration: "0.7s" }} viewBox="0 0 24 24" fill="none">
        <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/** VoI Efficiency Badge shown in the page header. */
export function GlobalEfficiencyBadge({ savingsPercent }) {
  const isHigh = savingsPercent >= 60;
  const isMid  = savingsPercent >= 20;

  const color = isHigh
    ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/8"
    : isMid
      ? "text-amber-400 border-amber-500/20 bg-amber-500/8"
      : "text-slate-400 border-slate-600/30 bg-slate-800/40";

  const dotColor = isHigh ? "bg-emerald-400" : isMid ? "bg-amber-400" : "bg-slate-500";

  return (
    <div
      className={`flex items-center gap-2 border px-3.5 py-2 rounded-xl cursor-help transition-all duration-500 ${color}`}
      title="Percentage of redundant network updates filtered by the Value-of-Information (VoI) algorithm."
    >
      <div className={`w-1.5 h-1.5 rounded-full ${dotColor} animate-pulse`} />
      <span className="text-[10px] font-black uppercase tracking-widest opacity-70">VoI</span>
      <span className="text-sm font-mono font-black">{savingsPercent.toFixed(1)}%</span>
    </div>
  );
}
