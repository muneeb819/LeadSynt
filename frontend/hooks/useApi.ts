"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** Small data-fetching hook: GET via the API client with refresh support. */
export function useApi<T>(path: string | (() => string), deps: unknown[] = []): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  const refresh = useCallback(() => {
    const id = ++seq.current;
    const p = typeof path === "function" ? path() : path;
    if (!p) {
      // Empty path = skip fetching (conditional endpoints).
      setLoading(false);
      return;
    }
    setLoading(true);
    api<T>(p)
      .then((d) => {
        if (seq.current === id) {
          setData(d);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (seq.current === id) setError(e.message);
      })
      .finally(() => {
        if (seq.current === id) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh };
}
