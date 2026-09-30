import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MetricType } from "web-vitals";
import type { WebVitalBatchCreate } from "../lib/generated";
import {
  createResearchRumReporter,
  researchRumRoute,
  rumViewportClass,
  sendResearchRum,
  webVitalSample,
} from "../lib/rum";

function metric(overrides: Partial<MetricType> = {}): MetricType {
  return {
    delta: 2400,
    entries: [],
    id: "v4-private-client-id",
    name: "LCP",
    navigationId: 0,
    navigationType: "navigate",
    rating: "good",
    value: 2400,
    ...overrides,
  } as MetricType;
}

describe("research workbench RUM", () => {
  beforeEach(() => {
    window.history.replaceState(
      null,
      "",
      "/workspace/research?view=pipeline&q=secret-query&entity=11111111-1111-4111-8111-111111111111",
    );
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement the browser Cookie Store API.
    document.cookie = "pharma_csrf=rum-csrf";
  });

  it("maps navigation URLs to bounded routes without transmitting query or identity data", () => {
    const sample = webVitalSample(
      metric({
        navigationURL:
          "http://localhost:3000/workspace/research?view=drug&q=private-term&entity=22222222-2222-4222-8222-222222222222",
      }),
      undefined,
      390,
    );

    expect(sample).toEqual({
      metric_name: "LCP",
      navigation_sequence: 0,
      navigation_type: "navigate",
      rating: "good",
      route: "drug",
      value: 2400,
      viewport_class: "mobile",
    });
    const serialized = JSON.stringify(sample);
    expect(serialized).not.toContain("private-term");
    expect(serialized).not.toContain("22222222");
    expect(serialized).not.toContain("v4-private-client-id");
    expect(researchRumRoute("https://outside.example/workspace/research?view=drug")).toBe("unknown");
    expect(researchRumRoute("/workspace/research?view=internal-secret")).toBe("unknown");
    expect(researchRumRoute("/?q=private-login-state")).toBe("overview");
    expect(researchRumRoute("/research.html?entity=private-entity")).toBe("overview");
    expect(rumViewportClass(1024)).toBe("tablet");
  });

  it("uses the authenticated keepalive boundary with a bounded privacy payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 202 }));
    const sample = webVitalSample(metric());
    expect(sample).not.toBeNull();
    if (!sample) throw new Error("Expected a valid LCP sample");
    const batch: WebVitalBatchCreate = {
      schema_version: 1,
      samples: [sample],
    };

    await expect(sendResearchRum(batch, true)).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [path, init] = fetchMock.mock.calls[0] ?? [];
    expect(path).toBe("/api/v1/workspace/web-vitals");
    expect(init?.keepalive).toBe(true);
    expect(init?.credentials).toBe("same-origin");
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("rum-csrf");
    expect(JSON.parse(String(init?.body))).toEqual(batch);
  });

  it("does not turn a telemetry authorization failure into a session logout", async () => {
    const unauthorized = vi.fn();
    window.addEventListener("pharma:unauthorized", unauthorized);
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ detail: "Session expired" }), { status: 401 }));
    const sample = webVitalSample(metric());
    expect(sample).not.toBeNull();
    if (!sample) throw new Error("Expected a valid LCP sample");
    const batch: WebVitalBatchCreate = { schema_version: 1, samples: [sample] };

    await expect(sendResearchRum(batch, true)).resolves.toBe(false);
    await expect(sendResearchRum(batch, false)).resolves.toBe(false);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(unauthorized).not.toHaveBeenCalled();
    window.removeEventListener("pharma:unauthorized", unauthorized);
  });

  it("deduplicates metric updates and sends no more than eight samples per batch", async () => {
    const batches: WebVitalBatchCreate[] = [];
    const reporter = createResearchRumReporter(async (batch) => {
      batches.push(batch);
      return true;
    });
    reporter.report(metric({ value: 2499 }));
    reporter.report(metric({ value: 2400 }));
    for (let navigationId = 1; navigationId <= 8; navigationId += 1) {
      reporter.report(metric({ navigationId }));
    }

    expect(reporter.pendingCount()).toBe(9);
    await expect(reporter.flush(false)).resolves.toBe(true);
    expect(batches[0]?.samples).toHaveLength(8);
    expect(batches[0]?.samples[0]?.value).toBe(2400);
    expect(reporter.pendingCount()).toBe(1);
    await expect(reporter.flush(false)).resolves.toBe(true);
    expect(batches[1]?.samples).toHaveLength(1);
    reporter.dispose();
  });
});
