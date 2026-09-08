"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./client";

export type Poll<T> = {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  refresh: () => void;
};

/**
 * Polls a backend read while the tab is open.
 *
 * Matching itself does not depend on this: the worker refreshes a candidate's
 * recommendations whether or not a browser is connected. Polling only decides
 * how quickly an open tab notices a new revision, so it stops as soon as
 * `isSettled` says the value will not change again, and never retries a request
 * the backend called permanent.
 *
 * `load` and `isSettled` must be stable (useCallback or a module constant):
 * they are effect dependencies, and a new identity restarts the poll.
 */
export function usePolling<T>(
  load: () => Promise<T>,
  options: { intervalMs?: number; isSettled?: (value: T) => boolean; enabled?: boolean } = {},
): Poll<T> {
  const { intervalMs = 5000, isSettled, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const run = async () => {
      try {
        const value = await load();
        if (!active) return;
        setData(value);
        setError(null);
        if (!isSettled || !isSettled(value)) {
          timer = setTimeout(run, intervalMs);
        }
      } catch (caught) {
        if (!active) return;
        const apiError =
          caught instanceof ApiError
            ? caught
            : new ApiError(0, "UNEXPECTED_ERROR", "The request failed.", false);
        setError(apiError);
        // Retrying a 403 or a 501 would only repeat the same answer.
        if (apiError.retryable) {
          timer = setTimeout(run, intervalMs);
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void run();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [enabled, intervalMs, isSettled, load, tick]);

  return { data, error, loading, refresh };
}
