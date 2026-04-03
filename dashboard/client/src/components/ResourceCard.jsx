import React from "react";

function isNumeric(val) {
  return !isNaN(parseFloat(val)) && isFinite(val);
}

/**
 * ResourceCard — 2×2 grid card used in the Node Inspector panel.
 * Displays a single resource metric with a mini progress bar.
 * An amber dot is shown when the VoI filter suppressed the update this round.
 */
export function ResourceCard({ label, value, unit = "", icon, isFiltered }) {
  const displayValue = isNumeric(value) ? parseFloat(value).toFixed(2) : value;

  const barColor = isNumeric(value)
    ? (value > 80 ? "bg-red-500" : value > 50 ? "bg-amber-500" : "bg-emerald-500")
    : "bg-slate-700";

  return (
    <div className="relative bg-slate-900/50 border border-slate-700/50 rounded-xl p-3 flex flex-col gap-1 overflow-hidden transition-all hover:bg-slate-900/80">
      {isFiltered && (
        <div className="absolute top-1.5 right-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse"
            title="VoI Filtered (Stale Value)"
          />
        </div>
      )}
      <div className="flex items-center gap-2 text-slate-500">
        {icon}
        <span className="text-[9px] font-bold uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1 mt-0.5">
        <span className={`text-lg font-mono font-bold ${isFiltered ? "text-slate-400" : "text-white"}`}>
          {displayValue}
        </span>
        <span className="text-[9px] text-slate-600 font-medium">{unit}</span>
      </div>
      <div className="mt-2 w-full h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-700 ${barColor}`}
          style={{ width: `${isNumeric(value) ? Math.min(value, 100) : 0}%` }}
        />
      </div>
    </div>
  );
}
