import { afterEach, expect, it, vi } from "vitest";

import {
  loadCommercialBilling,
  loadCommercialClients,
  loadCommercialDisputes,
  loadCommercialExports,
  loadCommercialOverview,
  loadCommercialRiskPage,
  loadLifecycleWorkspace,
} from "../lib/contracts/commercial";

afterEach(() => vi.restoreAllMocks());

function json(payload: unknown): Response {
  return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
}

it("uses generated commercial routes and preserves operator filters", async () => {
  const urls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    urls.push(url);
    return json(
      url.endsWith("/overview")
        ? { as_of: "2026-07-19T00:00:00Z", open_risk_count: 0, period_start: "2026-07-19", subscriptions: [] }
        : [],
    );
  });

  await Promise.all([
    loadCommercialOverview(),
    loadCommercialClients(),
    loadCommercialBilling("dead"),
    loadCommercialDisputes("investigating"),
    loadCommercialExports(),
  ]);

  expect(urls).toHaveLength(6);
  expect(urls.some((url) => url.includes("/billing-deliveries?") && url.includes("delivery_state=dead"))).toBe(true);
  expect(urls.some((url) => url.includes("/billing-disputes?") && url.includes("dispute_status=investigating"))).toBe(
    true,
  );
});

it("cancels both billing-pane requests when the owning query is abandoned", async () => {
  const signals: AbortSignal[] = [];
  let resolveStarted: () => void = () => undefined;
  const started = new Promise<void>((resolve) => {
    resolveStarted = resolve;
  });
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    const signal = init?.signal;
    if (!(signal instanceof AbortSignal)) throw new Error("Expected a request AbortSignal");
    signals.push(signal);
    if (signals.length === 2) resolveStarted();
    return new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  });
  const controller = new AbortController();

  const workspace = loadCommercialBilling("all", controller.signal);
  await started;
  controller.abort();

  await expect(workspace).rejects.toBeDefined();
  expect(signals).toHaveLength(2);
  expect(signals.every((signal) => signal.aborted)).toBe(true);
});

it("loads a bounded commercial risk page with its signed cursor", async () => {
  const urls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    urls.push(String(input));
    return json({ items: [], total_items: 80, next_cursor: "next-signed-cursor" });
  });

  const page = await loadCommercialRiskPage("open", "current-signed-cursor");

  expect(page.total_items).toBe(80);
  expect(urls).toHaveLength(1);
  expect(urls[0]).toContain("/api/v1/commercial/risk-events/page?");
  expect(urls[0]).toContain("case_status=open");
  expect(urls[0]).toContain("limit=25");
  expect(urls[0]).toContain("cursor=current-signed-cursor");
});

it("does not enumerate lifecycle purge candidates without active retention policies", async () => {
  const urls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    urls.push(String(input));
    return json([]);
  });

  const workspace = await loadLifecycleWorkspace();

  expect(urls).toHaveLength(4);
  expect(urls.some((url) => url.includes("export-candidates"))).toBe(false);
  expect(urls.some((url) => url.includes("source-candidates"))).toBe(false);
  expect(workspace.purgeCandidates).toEqual([]);
  expect(workspace.sourcePurgeCandidates).toEqual([]);
});

it("loads both governed purge candidate sets when their retention policies are active", async () => {
  const urls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    urls.push(url);
    if (url.includes("retention-policies")) {
      return json([
        { active: true, data_class: "commercial_export_artifact" },
        { active: true, data_class: "source_asset_snapshot" },
      ]);
    }
    return json([]);
  });

  await loadLifecycleWorkspace();

  expect(urls).toHaveLength(6);
  expect(urls.some((url) => url.includes("export-candidates"))).toBe(true);
  expect(urls.some((url) => url.includes("source-candidates"))).toBe(true);
});
