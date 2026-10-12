import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

// Load JSON from the API, with loading/error state and optional auto-refresh.
export function useApi(path, { refreshMs = 0 } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const latest = useRef(path);

  const load = useCallback(async () => {
    if (!path) return;
    latest.current = path;
    try {
      const result = await api.get(path);
      if (latest.current === path) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (latest.current === path) setError(e);
    } finally {
      if (latest.current === path) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setLoading(true);
    load();
    if (!refreshMs) return undefined;
    const timer = setInterval(load, refreshMs);
    return () => clearInterval(timer);
  }, [load, refreshMs]);

  return { data, error, loading, reload: load };
}
