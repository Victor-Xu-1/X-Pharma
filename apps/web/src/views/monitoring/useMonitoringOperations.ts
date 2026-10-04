import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { loadMonitoringAlertReplay, loadMonitoringTopicReplay, type SavedSearch } from "../../lib/contracts/monitoring";

export function useMonitoringOperations(tab: string, onOpenSearch: (saved: SavedSearch) => void) {
  const live = useRef({ mounted: true, tab, generation: 0, open: onOpenSearch });
  const locks = useRef(new Set<string>());
  const [pending, setPending] = useState(new Set<string>());
  const [error, setError] = useState("");
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
    setError("");
    try {
      await request();
      if (live.current.mounted) await after?.();
    } catch (caught) {
      if (live.current.mounted && live.current.generation === generation)
        setError(caught instanceof Error ? caught.message : "监控操作失败");
    } finally {
      locks.current.delete(key);
      if (live.current.mounted) setPending(new Set(locks.current));
    }
  }
  function replay(kind: "topic" | "alert", id: string) {
    const generation = live.current.generation;
    return run(`replay:${kind}:${id}`, async () => {
      const saved = kind === "topic" ? await loadMonitoringTopicReplay(id) : await loadMonitoringAlertReplay(id);
      if (live.current.mounted && live.current.generation === generation) live.current.open(saved);
    });
  }
  return { pending, error, clearError: () => setError(""), run, replay };
}
