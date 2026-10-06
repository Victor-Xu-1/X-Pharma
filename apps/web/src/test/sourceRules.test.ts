import { describe, expect, it } from "vitest";
import { initialPublicSourceDraft, sourceRoutingRules } from "../views/dataFactory/sourceRules";

describe("public-source routing contracts", () => {
  it("requires explicit bounded activity enrichment and keeps disabled legacy rules unchanged", () => {
    const draft = {
      ...initialPublicSourceDraft(),
      targetChemblId: "CHEMBL203",
      includeActivities: true,
      maxRecords: 25,
      activityLimit: 5,
    };
    expect(sourceRoutingRules("chembl", draft)[0]).toEqual(
      expect.objectContaining({ include_activities: true, activity_limit: 5 }),
    );
    expect(() => sourceRoutingRules("chembl", { ...draft, activityLimit: 11 })).toThrow("1–10");
  });
  it("keeps continuous configuration explicit and preserves its bounded work budget", () => {
    const draft = {
      ...initialPublicSourceDraft(),
      queryTerm: "configured query",
      startDate: "2026-07-01",
      maxRecords: 25,
    };
    expect(sourceRoutingRules("clinicaltrials_gov", draft)).toEqual([
      {
        query_term: "configured query",
        max_records: 25,
        page_size: 100,
        sync_mode: "continuous",
        start_date: "2026-07-01",
        window_days: 31,
        overlap_days: 2,
        reconcile_interval_days: 30,
        sort: "LastUpdatePostDate:desc",
      },
    ]);
  });
  it("does not put query, date-window or credential fields into ChEMBL routing", () => {
    expect(sourceRoutingRules("chembl", { ...initialPublicSourceDraft(), targetChemblId: "chembl203" })).toEqual([
      { target_chembl_id: "CHEMBL203", max_records: 100, page_size: 100, sync_mode: "continuous" },
    ]);
  });
  it("leaves PubMed metadata snapshots distinct from exhaustive synchronization", () => {
    expect(sourceRoutingRules("pubmed", { ...initialPublicSourceDraft(), queryTerm: "configured query" })).toEqual([
      { query_term: "configured query", max_records: 100, page_size: 100, include_abstract: false },
    ]);
  });
  it("does not submit blank queries, fractional budgets or invalid target IDs", () => {
    expect(() => sourceRoutingRules("clinicaltrials_gov", initialPublicSourceDraft())).toThrow("检索主题不能为空");
    expect(() =>
      sourceRoutingRules("chembl", { ...initialPublicSourceDraft(), targetChemblId: "https://untrusted.test" }),
    ).toThrow("靶点编号");
    expect(() =>
      sourceRoutingRules("pubmed", { ...initialPublicSourceDraft(), queryTerm: "x", maxRecords: 1.5 }),
    ).toThrow("整数");
  });
});
