import { afterEach, beforeEach, expect, it, vi } from "vitest";

class FakeWorker {
  static latest: FakeWorker;

  readonly messages: unknown[] = [];
  readonly terminate = vi.fn();
  private messageListener?: (event: MessageEvent<unknown>) => void;
  private errorListener?: (event: ErrorEvent) => void;

  constructor() {
    FakeWorker.latest = this;
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject): void {
    const callback = typeof listener === "function" ? listener : (event: Event) => listener.handleEvent(event);
    if (type === "message") this.messageListener = callback as (event: MessageEvent<unknown>) => void;
    if (type === "error") this.errorListener = callback as (event: ErrorEvent) => void;
  }

  postMessage(message: unknown): void {
    this.messages.push(message);
  }

  emitMessage(data: unknown): void {
    this.messageListener?.({ data } as MessageEvent<unknown>);
  }

  emitError(): void {
    this.errorListener?.(new Event("error") as ErrorEvent);
  }
}

beforeEach(() => {
  vi.resetModules();
  vi.stubGlobal("Worker", FakeWorker);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("returns a validated rendering from the isolated worker", async () => {
  const { renderMolecule } = await import("../lib/rdkitRenderer");
  const resultPromise = renderMolecule(" CCO ");
  const request = FakeWorker.latest.messages[0] as { id: string; smiles: string };
  expect(request.smiles).toBe("CCO");

  FakeWorker.latest.emitMessage({
    id: request.id,
    ok: true,
    svg: "<svg></svg>",
    version: "2025.03.4",
  });

  await expect(resultPromise).resolves.toEqual({ svg: "<svg></svg>", version: "2025.03.4" });
});

it("rejects every pending request when the worker fails", async () => {
  const { renderMolecule } = await import("../lib/rdkitRenderer");
  const resultPromise = renderMolecule("CCO");
  FakeWorker.latest.emitError();

  await expect(resultPromise).rejects.toThrow("RDKit renderer is unavailable");
  expect(FakeWorker.latest.terminate).toHaveBeenCalledOnce();
});

it("rejects oversized structures before creating a worker", async () => {
  const { renderMolecule } = await import("../lib/rdkitRenderer");
  await expect(renderMolecule("C".repeat(4_097))).rejects.toThrow("exceeds the rendering limit");
});
