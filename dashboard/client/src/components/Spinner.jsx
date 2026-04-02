import React from "react";

/** Loading spinner — animated SVG. */
export function Spinner() {
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

/** VoI Efficiency Badge shown in the page header. */
export function GlobalEfficiencyBadge({ savingsPercent }) {
  return (
    <div
      className="flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg shadow-inner cursor-help"
      title="Percentage of redundant network updates successfully filtered by the Value-of-Information logic."
    >
      <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">VoI Efficiency</span>
      <span className="text-sm font-mono font-bold text-emerald-300">{savingsPercent.toFixed(1)}%</span>
    </div>
  );
}
