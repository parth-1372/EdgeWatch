import { useState, useCallback } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "") + "/api";

/**
 * useConfig — manages config.ini fetch, local edits, and save-back.
 *
 * Fix (CodeRabbit, Minor): config starts as null; callers must guard
 * against null before calling Object.entries(config).
 */
export function useConfig() {
  const [config, setConfig]       = useState(null);
  const [loading, setLoading]     = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [saving, setSaving]       = useState(false);

  // Fetch on mount
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await fetch(`${API_BASE}/config`);
      const data = await res.json();

      if (!res.ok || data.error) {
        throw new Error(data.error || `Server returned ${res.status}`);
      }

      setConfig(data);
    } catch (err) {
      setFetchError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = useCallback((section, key, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: { ...prev[section], [key]: value },
    }));
  }, []);

  const handleSave = useCallback(async (onSuccess, onError) => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!res.ok) {
        let errorMsg = "Save error";
        try {
          const errorData = await res.json();
          errorMsg = errorData.error || errorData.details || errorMsg;
        } catch (e) {
          try {
            const text = await res.text();
            if (text) errorMsg = text;
          } catch (e2) { /* ignore */ }
        }
        throw new Error(errorMsg);
      }

      onSuccess?.("Configuration cached.");
    } catch (err) {
      onError?.(err.message);
    } finally {
      setSaving(false);
    }
  }, [config]);

  return {
    config,
    loading,
    fetchError,
    saving,
    fetchConfig,
    handleChange,
    handleSave,
  };
}
