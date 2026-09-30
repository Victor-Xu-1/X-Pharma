import { expect, it, vi } from "vitest";

import { loadOverview } from "../lib/contracts/overview";

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}

it("does not issue operations or governance requests from the research overview", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path.startsWith("/api/v1/entities")) {
      return json({
        items: [],
        total: 7,
        limit: 1,
        offset: 0,
        facets: { entity_type: { target: 5, drug: 2 }, review_status: { verified: 6, draft: 1 } },
        suggestions: [],
        engine: "opensearch",
      });
    }
    if (path.startsWith("/api/v1/knowledge/pages")) return json([]);
    if (path.startsWith("/api/v1/workspace/recent-entities")) return json([]);
    return json({ detail: `Unexpected request: ${path}` }, 500);
  });

  const snapshot = await loadOverview();

  expect(snapshot.entityTotal).toBe(7);
  expect(snapshot.entityTypeCounts).toEqual({ target: 5, drug: 2 });
  expect(snapshot.reviewStatusCounts).toEqual({ verified: 6, draft: 1 });
  expect(snapshot.pages).toEqual([]);
  expect(snapshot.recentEntities).toEqual([]);
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/admin/"))).toBe(false);
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/governance/"))).toBe(false);
});

it("fails explicitly when a core research metric is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    if (path.startsWith("/api/v1/entities")) {
      return json({ items: [], total: 3, limit: 1, offset: 0, facets: {}, suggestions: [], engine: "opensearch" });
    }
    if (path.startsWith("/api/v1/knowledge/pages")) return json({ detail: "Knowledge unavailable" }, 503);
    if (path.startsWith("/api/v1/workspace/recent-entities")) return json([]);
    return json({ detail: `Unexpected request: ${path}` }, 500);
  });

  await expect(loadOverview()).rejects.toThrow("核心情报指标暂不可用");
});
