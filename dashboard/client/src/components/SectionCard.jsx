import React from "react";

/** Convert an INI section key like 'node_range' into a readable label. */
function sectionLabel(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

const SECTION_META = {
  PriomonParam:   { accent: "from-violet-500/20 to-indigo-600/20", border: "border-violet-500/30", text: "text-violet-400" },
  system_setting: { accent: "from-cyan-500/20 to-sky-600/20",     border: "border-cyan-500/30",   text: "text-cyan-400"   },
  database:       { accent: "from-amber-500/20 to-orange-600/20", border: "border-amber-500/30",  text: "text-amber-400"  },
};

const DEFAULT_META = { accent: "from-slate-500/20 to-slate-700/20", border: "border-slate-500/30", text: "text-slate-400" };

/**
 * SectionCard — renders one INI section with editable text inputs.
 * Keys starting with ";" are treated as comments and skipped.
 */
export function SectionCard({ sectionKey, sectionData, onChange }) {
  const meta = SECTION_META[sectionKey] || DEFAULT_META;

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
          const strVal  = value === null || value === undefined ? "" : String(value);

          return (
            <div key={key} className="flex flex-col gap-2">
              <label htmlFor={inputId} className="text-[9px] font-bold text-slate-500 uppercase tracking-widest pl-1">
                {sectionLabel(key)}
              </label>
              <input
                id={inputId}
                type="text"
                value={strVal}
                onChange={e => onChange(sectionKey, key, e.target.value)}
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
