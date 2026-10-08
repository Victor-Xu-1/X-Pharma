import { expect, type Page, test } from "@playwright/test";
import { installBrowserQualityProbe } from "./workspace/helpers";

type Timing = { interactionId: number; duration: number };
type Probe = { interaction_ids: Set<number>; inp_ms: number };

async function installedProbe() {
  const fakeWindow: { __pharmaBrowserQuality?: Probe } = {};
  const observers = new Map<string, (entries: Timing[]) => void>();
  const saved = ["window", "PerformanceObserver"].map(
    (name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const,
  );
  Object.defineProperty(globalThis, "window", { configurable: true, value: fakeWindow });
  Object.defineProperty(globalThis, "PerformanceObserver", {
    configurable: true,
    value: class {
      private readonly callback: (list: { getEntries: () => Timing[] }) => void;
      constructor(callback: (list: { getEntries: () => Timing[] }) => void) {
        this.callback = callback;
      }
      observe(options: { type: string }) {
        observers.set(options.type, (entries) => this.callback({ getEntries: () => entries }));
      }
    },
  });
  const page = {
    addInitScript: async (initialize: () => void) => initialize(),
  } as unknown as Page;
  try {
    await installBrowserQualityProbe(page);
  } finally {
    for (const [name, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
  if (!fakeWindow.__pharmaBrowserQuality) throw new Error("Probe was not installed");
  return { probe: fakeWindow.__pharmaBrowserQuality, observers };
}

test("[quality-probe-contract] records the actual first input below the ordinary event duration threshold", async () => {
  const { probe, observers } = await installedProbe();
  expect(observers.has("first-input")).toBe(true);
  observers.get("first-input")?.([{ interactionId: 7, duration: 8 }]);
  expect(probe.interaction_ids.size).toBe(1);
  expect(probe.inp_ms).toBe(8);
});

test("[quality-probe-contract] deduplicates first-input and ordinary event reports without changing durations", async () => {
  const { probe, observers } = await installedProbe();
  observers.get("first-input")?.([{ interactionId: 7, duration: 8 }]);
  observers.get("event")?.([{ interactionId: 7, duration: 24 }]);
  expect(probe.interaction_ids.size).toBe(1);
  expect(probe.inp_ms).toBe(24);
});

test("[quality-probe-contract] does not invent a measurement without an actual interaction", async () => {
  const { probe, observers } = await installedProbe();
  observers.get("event")?.([{ interactionId: 0, duration: 999 }]);
  expect(probe.interaction_ids.size).toBe(0);
  expect(probe.inp_ms).toBe(0);
});
