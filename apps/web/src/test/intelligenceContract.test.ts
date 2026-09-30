import { expect, it, vi } from "vitest";

import { lookupEntityTypes, saveEntitySearch } from "../lib/contracts/intelligence";

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });
}

it("looks up one governed entity across an explicit bounded type set", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.entity.search.v2",
      applied_filters: [],
      items: [
        {
          id: "550e8400-e29b-41d4-a716-446655440002",
          canonical_entity_id: "550e8400-e29b-41d4-a716-446655440002",
          entity_type: "target",
          name: "EGFR",
          description: null,
          external_ids: { HGNC: "3236" },
          aliases: ["ERBB1"],
          attributes: {},
          match: null,
          review_status: "verified",
          created_at: "2026-07-30T00:00:00Z",
          updated_at: "2026-07-30T00:00:00Z",
        },
      ],
      total: 1,
      limit: 10,
      offset: 0,
      facets: {},
      suggestions: [],
      engine: "opensearch",
      took_ms: 3,
      sort_by: "relevance",
      sort_direction: "desc",
      sort: [],
    }),
  );

  await expect(lookupEntityTypes(" EGFR ", ["drug", "target", "disease", "organization"])).resolves.toHaveLength(1);
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/entities");
  expect(requestUrl.searchParams.getAll("entity_types")).toEqual(["disease", "drug", "organization", "target"]);
  expect(requestUrl.searchParams.get("review_status")).toBe("verified");
  expect(requestUrl.searchParams.get("limit")).toBe("10");
});

it("reports partial success without repeating a persisted saved search", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path === "/api/v1/monitoring/saved-searches") {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        query: {
          q: "EGFR",
          entity_type: "target",
          review_status: "verified",
          display_mode: "landscape",
          analysis_view: "table",
        },
      });
      return json({
        created_at: "2026-07-18T10:00:00Z",
        description: "",
        id: "saved-search-1",
        name: "EGFR landscape",
        owner_user_id: "user-1",
        query_json: { q: "EGFR", entity_type: "target" },
        query_type: "entity_search",
        query_version: 1,
        updated_at: "2026-07-18T10:00:00Z",
        visibility: "private",
      });
    }
    if (path === "/api/v1/monitoring/topics") {
      expect(init?.method).toBe("POST");
      return json({ detail: "Monitoring unavailable" }, 503);
    }
    return json({ detail: `Unexpected request: ${path}` }, 500);
  });

  const result = await saveEntitySearch({
    name: " EGFR landscape ",
    query: " EGFR ",
    entityTypes: ["target"],
    reviewStatus: "verified",
    sortBy: "name",
    sortDirection: "asc",
    displayMode: "landscape",
    analysisView: "table",
    shared: false,
    monitor: true,
  });

  expect(result.message).toBe("检索已保存，但监控未启用：Monitoring unavailable");
  expect(fetchMock).toHaveBeenCalledTimes(2);
  expect(fetchMock.mock.calls.filter(([input]) => String(input) === "/api/v1/monitoring/saved-searches")).toHaveLength(
    1,
  );
});
