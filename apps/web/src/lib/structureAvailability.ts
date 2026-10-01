type StructureAvailabilitySource = {
  subscribe: (changed: () => void) => () => void;
  read: (signal: AbortSignal) => Promise<string>;
  update: (hasStructure: boolean) => void;
  fail: (error: unknown) => void;
};

/** Observe completed editor changes, not pointer events that precede drawing. */
export function observeStructureAvailability(source: StructureAvailabilitySource): () => void {
  const controller = new AbortController();
  let revision = 0;
  let reading = false;
  let queued = false;

  async function drain() {
    if (reading || controller.signal.aborted) return;
    reading = true;
    try {
      while (queued && !controller.signal.aborted) {
        queued = false;
        const current = revision;
        try {
          const structure = await source.read(controller.signal);
          if (!controller.signal.aborted && current === revision) source.update(Boolean(structure.trim()));
        } catch (error) {
          if (!controller.signal.aborted && current === revision) {
            source.update(false);
            source.fail(error);
          }
        }
      }
    } finally {
      reading = false;
    }
  }

  function changed() {
    revision += 1;
    queued = true;
    void drain();
  }

  const unsubscribe = source.subscribe(changed);
  changed();
  return () => {
    controller.abort();
    unsubscribe();
  };
}
