import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  loadMonitoringAlertReplay,
  loadMonitoringTopicReplay,
  loadSavedSearch,
  type SavedSearch,
} from "../../lib/contracts/monitoring";
import { useMessages } from "../../lib/i18n";
import { monitoringMessages } from "../../lib/i18n/monitoring";

export function useMonitoringOperations(tab: string, onOpenSearch: (saved: SavedSearch) => void) {
  const text = useMessages(monitoringMessages);
  const live = useRef({ mounted: true, tab, generation: 0, open: onOpenSearch });
  const locks = useRef(new Set<string>());
  const replayIntent = useRef(0);
  const [pending, setPending] = useState(new Set<string>());
  const [error, setError] = useState<{ raw: string } | { fallback: true } | null>(null);
  useLayoutEffect(() => {
    if (live.current.tab !== tab) live.current.generation += 1;
    live.current.tab = tab;
    live.current.open = onOpenSearch;
  });
  useEffect(() => {
    live.current.mounted = true;
    return () => {
      live.current.mounted = false;
      live.current.generation += 1;
    };
  }, []);
  async function run(key: string, request: () => Promise<unknown>, after?: () => Promise<void> | void) {
    if (locks.current.has(key)) return;
    locks.current.add(key);
    const generation = live.current.generation;
    setPending(new Set(locks.current));
    setError(null);
    try {
      await request();
      if (live.current.mounted) await after?.();
    } catch (caught) {
      if (live.current.mounted && live.current.generation === generation)
        setError(caught instanceof Error ? { raw: caught.message } : { fallback: true });
    } finally {
      locks.current.delete(key);
      if (live.current.mounted) setPending(new Set(locks.current));
    }
  }
  function replay(kind: "topic" | "alert" | "saved", id: string) {
    const key = `replay:${kind}:${id}`;
    if (locks.current.has(key)) return Promise.resolve();
    const generation = live.current.generation;
    const intent = ++replayIntent.current;
    const isCurrent = () =>
      live.current.mounted && live.current.generation === generation && replayIntent.current === intent;
    return run(key, async () => {
      try {
        const saved =
          kind === "topic"
            ? await loadMonitoringTopicReplay(id)
            : kind === "alert"
              ? await loadMonitoringAlertReplay(id)
              : await loadSavedSearch(id);
        if (isCurrent()) live.current.open(saved);
      } catch (caught) {
        if (isCurrent()) throw caught;
      }
    });
  }
  return {
    pending,
    error: error ? ("raw" in error ? error.raw : text("监控操作失败")) : "",
    clearError: () => setError(null),
    run,
    replay,
  };
}
