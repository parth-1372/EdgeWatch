import React from "react";
import { useState, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:5000/api";

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
// Section card — renders one INI section dynamically
// ---------------------------------------------------------------------------
function SectionCard({ sectionKey, sectionData, onChange }) {
  // Section colours mapped by index order
  const sectionMeta = {
    PriomonParam: { accent: "from-violet-500 to-indigo-600", dot: "bg-violet-400" },
    system_setting: { accent: "from-cyan-500 to-sky-600", dot: "bg-cyan-400" },
    database: { accent: "from-amber-500 to-orange-600", dot: "bg-amber-400" },
  };

  const meta = sectionMeta[sectionKey] || {
    accent: "from-slate-500 to-slate-700",
    dot: "bg-slate-400",
  };

  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/50 backdrop-blur-sm overflow-hidden shadow-xl">
      {/* Card header */}
      <div className={`bg-gradient-to-r ${meta.accent} px-6 py-4 flex items-center gap-3`}>
        <span className={`w-2.5 h-2.5 rounded-full ${meta.dot} shadow-lg`} />
        <h2 className="text-white font-semibold text-base tracking-wide font-mono">
          [{sectionKey}]
        </h2>
      </div>

      {/* Key-value fields */}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        {Object.entries(sectionData).map(([key, value]) => {
          // Skip comment-only keys produced by the ini parser (start with ;)
          if (key.startsWith(";")) return null;

          const inputId = `${sectionKey}__${key}`;
          const strVal = value === null || value === undefined ? "" : String(value);

          return (
            <div key={key} className="flex flex-col gap-1.5">
              <label
                htmlFor={inputId}
                className="text-xs font-semibold text-slate-400 uppercase tracking-widest"
              >
                {sectionLabel(key)}
              </label>
              <input
                id={inputId}
                type="text"
                value={strVal}
                onChange={(e) => onChange(sectionKey, key, e.target.value)}
                className="
                  bg-slate-900/70 border border-slate-600/60 rounded-lg px-4 py-2.5
                  text-slate-100 text-sm font-mono placeholder-slate-600
                  focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500
                  transition-all duration-150
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
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [booting, setBooting] = useState(false);
  const [toast, setToast] = useState(null); // { message, type }

  // ---- Load config on mount ------------------------------------------------
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/config`);
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        const data = await res.json();
        setConfig(data);
      } catch (err) {
        setFetchError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ---- Field change handler ------------------------------------------------
  const handleChange = useCallback((section, key, value) => {
    setConfig((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }));
  }, []);

  // ---- Save config ---------------------------------------------------------
  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Unknown error");
      setToast({ message: "Configuration saved successfully.", type: "success" });
    } catch (err) {
      setToast({ message: `Save failed: ${err.message}`, type: "error" });
    } finally {
      setSaving(false);
    }
  };

  // ---- Start experiment ----------------------------------------------------
  const handleStart = async () => {
    setBooting(true);
    try {
      const res = await fetch(`${API_BASE}/start`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Orchestrator error");
      setToast({ message: "Live network booted successfully!", type: "success" });
    } catch (err) {
      setToast({ message: `Boot failed: ${err.message}`, type: "error" });
    } finally {
      setBooting(false);
    }
  };

  // ---- Render loading / error states --------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 text-sm font-medium tracking-wide">
            Loading configuration…
          </p>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="bg-red-900/30 border border-red-700/50 rounded-2xl p-8 max-w-md text-center">
          <p className="text-red-400 font-semibold text-lg mb-2">Failed to load configuration</p>
          <p className="text-red-300/70 text-sm font-mono">{fetchError}</p>
          <p className="text-slate-500 text-xs mt-4">
            Is the API server running on <span className="text-slate-300 font-mono">localhost:5000</span>?
          </p>
        </div>
      </div>
    );
  }

  // ---- Main render ---------------------------------------------------------
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 selection:bg-violet-500/30">
      {/* Background radial glow */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-40 -left-40 w-[600px] h-[600px] bg-violet-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-[600px] h-[600px] bg-cyan-600/10 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-5xl mx-auto px-6 py-12">
        {/* ----------------------------------------------------------------- */}
        {/* Header */}
        {/* ----------------------------------------------------------------- */}
        <header className="mb-12">
          <div className="flex items-center gap-3 mb-1">
            {/* Logo mark */}
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
              </svg>
            </div>
            <span className="text-xs font-semibold tracking-[0.2em] text-violet-400 uppercase">
              PrioMon
            </span>
          </div>

          <h1 className="text-4xl font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent mt-3">
            Control Center
          </h1>
          <p className="text-slate-500 text-sm mt-1.5">
            Configure and launch the distributed monitoring network.
          </p>
        </header>

        {/* ----------------------------------------------------------------- */}
        {/* Config section cards — dynamically rendered */}
        {/* ----------------------------------------------------------------- */}
        <section className="space-y-6 mb-10">
          {Object.entries(config).map(([sectionKey, sectionData]) => {
            if (typeof sectionData !== "object" || sectionData === null) return null;
            return (
              <SectionCard
                key={sectionKey}
                sectionKey={sectionKey}
                sectionData={sectionData}
                onChange={handleChange}
              />
            );
          })}
        </section>

        {/* ----------------------------------------------------------------- */}
        {/* Action bar */}
        {/* ----------------------------------------------------------------- */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
          {/* Save button */}
          <button
            id="btn-save-config"
            onClick={handleSave}
            disabled={saving || booting}
            className="
              flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl
              bg-slate-700 hover:bg-slate-600 border border-slate-600 hover:border-slate-500
              text-slate-100 font-semibold text-sm
              transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            {saving ? (
              <>
                <Spinner />
                Saving…
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg>
                Save Configuration
              </>
            )}
          </button>

          {/* Start experiment button — prominent */}
          <button
            id="btn-start-experiment"
            onClick={handleStart}
            disabled={booting || saving}
            className="
              relative flex-1 flex items-center justify-center gap-3
              px-10 py-4 rounded-xl font-bold text-base tracking-wide
              bg-gradient-to-r from-violet-600 to-indigo-600
              hover:from-violet-500 hover:to-indigo-500
              text-white shadow-xl shadow-violet-500/30
              hover:shadow-violet-500/50 hover:scale-[1.01]
              active:scale-[0.99]
              transition-all duration-200
              disabled:opacity-60 disabled:cursor-not-allowed disabled:scale-100
              disabled:shadow-violet-500/10
            "
          >
            {/* Subtle animated ring when idle */}
            {!booting && (
              <span className="absolute inset-0 rounded-xl ring-1 ring-violet-400/30 animate-pulse" />
            )}

            {booting ? (
              <>
                <Spinner />
                Booting Network…
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728M8.464 15.536a5 5 0 010-7.072m7.072 0a5 5 0 010 7.072M12 12h.01" />
                </svg>
                Start Experiment
              </>
            )}
          </button>
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* Footer */}
        {/* ----------------------------------------------------------------- */}
        <footer className="mt-16 text-center text-slate-700 text-xs">
          PrioMon Control Center · API on{" "}
          <span className="font-mono text-slate-600">:5000</span> · Orchestrator on{" "}
          <span className="font-mono text-slate-600">:4000</span>
        </footer>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* Toast */}
      {/* ------------------------------------------------------------------- */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  );
}
