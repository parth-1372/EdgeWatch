import { useState, useCallback } from "react";

const API_BASE = "http://localhost:5000/api";

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
    try {
      const res  = await fetch(`${API_BASE}/config`);
      const data = await res.json();
      setConfig(data);
      setFetchError(null);
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
      if (!res.ok) throw new Error("Save error");
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
