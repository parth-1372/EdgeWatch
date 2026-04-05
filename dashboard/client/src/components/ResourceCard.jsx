import React from "react";

function isNumeric(val) {
  return !isNaN(parseFloat(val)) && isFinite(val);
}

const THRESHOLDS = {
  critical: { color: "text-red-400",    bar: "bg-gradient-to-r from-red-600 to-red-400",    glow: "shadow-[0_0_12px_rgba(239,68,68,0.3)]"     },
  warning:  { color: "text-amber-400",  bar: "bg-gradient-to-r from-amber-600 to-amber-400", glow: "shadow-[0_0_12px_rgba(245,158,11,0.3)]"    },
  good:     { color: "text-emerald-400",bar: "bg-gradient-to-r from-emerald-600 to-emerald-400", glow: "shadow-[0_0_12px_rgba(16,185,129,0.3)]" },
  neutral:  { color: "text-slate-400",  bar: "bg-slate-700",                                  glow: ""                                          },
};

function getThreshold(value) {
  if (!isNumeric(value)) return THRESHOLDS.neutral;
  const v = parseFloat(value);
  if (v > 80) return THRESHOLDS.critical;
  if (v > 50) return THRESHOLDS.warning;
  return THRESHOLDS.good;
}

/**
 * ResourceCard — 2×2 grid card used in the Node Inspector panel.
 * Displays a single resource metric with a mini progress bar.
 * An amber dot is shown when the VoI filter suppressed the update this round.
 */
export function ResourceCard({ label, value, unit = "", icon, isFiltered }) {
  const displayValue = isNumeric(value) ? parseFloat(value).toFixed(1) : (value === "not_updated" ? "—" : value ?? "—");
  const percent = isNumeric(value) ? Math.min(parseFloat(value), 100) : 0;
  const threshold = getThreshold(value);

  return (
    <div className={`relative glass rounded-2xl p-4 flex flex-col gap-2 overflow-hidden transition-all duration-300 hover:border-white/10 group ${isFiltered ? "opacity-70" : ""}`}>
      {/* VoI filter indicator */}
      {isFiltered && (
        <div className="absolute top-2.5 right-2.5" title="VoI Filtered — stale value held from last update">
          <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)] animate-pulse" />
        </div>
      )}

      {/* Label row */}
      <div className="flex items-center gap-1.5 text-slate-500">
        {icon}
        <span className="text-[9px] font-black uppercase tracking-widest">{label}</span>
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1">
        <span className={`text-xl font-mono font-black transition-colors duration-500 ${isFiltered ? "text-slate-500" : threshold.color}`}>
          {displayValue}
        </span>
        <span className="text-[9px] text-slate-600 font-medium">{unit}</span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1 bg-slate-800/80 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full bar-animate transition-all duration-700 ${threshold.bar}`}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Background glow on hover */}
      <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl ${threshold.glow}`} />
    </div>
  );
}
