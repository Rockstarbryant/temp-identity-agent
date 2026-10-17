"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCached, setCached } from "@/lib/cache";

interface Options {
  /** Re-fetch every N ms while mounted. 0 or undefined disables polling. */
  refreshMs?: number;
}

/**
 * Cached fetch hook. Returns cached data immediately (no spinner when you come
 * back to a page) and revalidates in the background.
 * `loading` is true only when there is nothing to show yet.
 */
export function useCachedData<T>(key: string | null, fetcher: () => Promise<T>, options: Options = {}) {
  const { refreshMs = 0 } = options;
  const [data, setData] = useState<T | undefined>(() => getCached<T>(key));
  const [error, setError] = useState<unknown>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refresh = useCallback(async (): Promise<T | undefined> => {
    if (!key) return undefined;
    try {
      const fresh = await fetcherRef.current();
      setCached(key, fresh);
      setData(fresh);
      setError(null);
      return fresh;
    } catch (err) {
      setError(err);
      return undefined;
    }
  }, [key]);

  // Optimistic local update (e.g. remove a deleted row) that also updates the cache.
  const mutate = useCallback(
    (updater: (prev: T | undefined) => T | undefined) => {
      setData((prev) => {
        const next = updater(prev);
        if (key && next !== undefined) setCached(key, next);
        return next;
      });
    },
    [key]
  );

  useEffect(() => {
    setData(getCached<T>(key));
    refresh();
  }, [key, refresh]);

  useEffect(() => {
    if (!refreshMs || !key) return;
    const id = setInterval(refresh, refreshMs);
    return () => clearInterval(id);
  }, [refreshMs, key, refresh]);

  return { data, error, loading: data === undefined && error === null, refresh, mutate };
}
