import { describe, expect, it } from "vitest";

import type { SavedSearch } from "../lib/contracts/monitoring";
import { savedSearchLocation } from "../workspaces/research/savedSearchLocation";

function saved(query_type: SavedSearch["query_type"], query_json: SavedSearch["query_json"]): SavedSearch {
  return {
    id: "62aecfaa-2d15-4a09-8d52-d69508c3f899",
    owner_user_id: "user-1",
    name: "Saved query",
    description: "",
    query_type,
    query_json,
    query_version: 1,
    visibility: "private",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  };
}

describe("saved-search location recovery", () => {
  it.each([
    ["entity_search", "explorer"],
    ["pipeline_search", "pipeline"],
    ["clinical_trial_search", "trials"],
    ["patent_search", "patents"],
    ["deal_search", "deals"],
    ["regulatory_search", "regulatory"],
    ["epidemiology_search", "epidemiology"],
    ["news_search", "news"],
  ] as const)("recovers %s in its own workspace without carrying another entity selection", (type, view) => {
    expect(savedSearchLocation(saved(type, { q: "EGFR" }))).toMatchObject({
      workbench: "research",
      view,
      query: "EGFR",
      entityId: null,
      invalidEntityId: false,
    });
  });

  it("keeps structure queries out of the URL and uses the authorized saved-query ID", () => {
    const item = saved("chemistry_search", { mode: "exact", query: "CCO", limit: 20 });
    expect(savedSearchLocation(item)).toMatchObject({
      view: "chemistry",
      query: "",
      chemistrySavedSearchId: item.id,
      invalidChemistrySavedSearchId: false,
    });
  });

  it("does not restore currency-free transaction amount sorting", () => {
    expect(savedSearchLocation(saved("deal_search", { q: "EGFR", sort: ["upfront_amount:desc"] }))).toMatchObject({
      dealSort: [{ field: "announced_at", direction: "desc" }],
      dealSortBy: "announced_at",
    });
  });

  it("preserves ordered multi-sort and exact boolean signal filters", () => {
    expect(
      savedSearchLocation(
        saved("pipeline_search", {
          q: "EGFR",
          sort: ["global_phase:desc", "drug_name:asc"],
          has_clinical_results: false,
          has_deal: true,
        }),
      ),
    ).toMatchObject({
      pipelineSort: [
        { field: "global_phase", direction: "desc" },
        { field: "drug_name", direction: "asc" },
      ],
      pipelineHasClinicalResults: "false",
      pipelineHasDeal: "true",
    });
  });
});
