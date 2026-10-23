import { describe, expect, it } from "vitest";
import {
  initialPublicSourceDraft,
  isPublicResearchSource,
  sourceRoutingRules,
  toLocalDateTimeInput,
} from "../views/dataFactory/sourceRules";

describe("public-source routing contracts", () => {
  it("does not classify prototype-like values as public source connectors", () => {
    expect(isPublicResearchSource("constructor" as Parameters<typeof isPublicResearchSource>[0])).toBe(false);
    expect(isPublicResearchSource("__proto__" as Parameters<typeof isPublicResearchSource>[0])).toBe(false);
  });
  it("leaves an unknown authorization timestamp blank instead of crashing or inventing a start time", () => {
    expect(toLocalDateTimeInput(null)).toBe("");
    expect(toLocalDateTimeInput("INVALID_SOURCE_DATE")).toBe("");
  });
  it("rejects impossible calendar dates and out-of-contract synchronization windows", () => {
    const draft = { ...initialPublicSourceDraft(), queryTerm: "Original query" };
    expect(() => sourceRoutingRules("clinicaltrials_gov", { ...draft, startDate: "2026-02-30" })).toThrow(
      "历史起始日期",
    );
    expect(() => sourceRoutingRules("clinicaltrials_gov", { ...draft, windowDays: 1.5 })).toThrow("日期分区");
    expect(() => sourceRoutingRules("clinicaltrials_gov", { ...draft, overlapDays: 31 })).toThrow("更新回看");
    expect(() => sourceRoutingRules("clinicaltrials_gov", { ...draft, reconcileIntervalDays: 0 })).toThrow(
      "完整复核周期",
    );
  });
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
