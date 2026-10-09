import { describe, expect, it } from "vitest";

import { canAccessView, canAccessWorkbench, parseWorkbenchLocation, workspaceUrl } from "../lib/workspaceRouting";
import { pipelineFiltersFromLocation } from "../workspaces/research/locationModel";

describe("workspace URL contract", () => {
  it.each([
    { tokens: ["status_date:desc"], canonicalTokens: [] },
    { tokens: ["phase:asc"], canonicalTokens: ["phase:asc"] },
    { tokens: ["phase:asc", "status_date:desc"], canonicalTokens: ["phase:asc", "status_date:desc"] },
  ])("preserves effective pipeline sort when canonicalizing $tokens", ({ tokens, canonicalTokens }) => {
    const params = new URLSearchParams({ view: "pipeline", q: "EGFR", analysis_dimension: "targets" });
    for (const token of tokens) params.append("sort", token);
    const original = parseWorkbenchLocation("research", `?${params}`);
    const canonical = new URL(workspaceUrl(original), "https://example.test");
    expect(canonical.searchParams.getAll("sort")).toEqual(canonicalTokens);
    const restored = parseWorkbenchLocation("research", canonical.search);
    expect(restored.pipelineSort).toEqual(original.pipelineSort);
    expect(pipelineFiltersFromLocation(restored).sort).toEqual(original.pipelineSort);
    expect(restored.query).toBe("EGFR");
    expect(restored.pipelineAnalysisDimension).toBe("targets");
  });

  it("round-trips explicit early and unknown stages without aliasing them to preclinical", () => {
    for (const stage of ["early_phase_1", "unknown"]) {
      const location = parseWorkbenchLocation("research", `?view=pipeline&phase=${stage}`);
      expect(location.phase).toBe(stage);
      expect(
        parseWorkbenchLocation(
          "research",
          workspaceUrl(location).split("?")[1] ? `?${workspaceUrl(location).split("?")[1]}` : "",
        ).phase,
      ).toBe(stage);
    }
  });

  it("keeps knowledge paging and filters across a deep-link round trip", () => {
    const location = parseWorkbenchLocation(
      "research",
      "?view=knowledge&q=EGFR&offset=550&page_type=target&sort_by=updated_at&sort_direction=desc",
    );
    expect(location.offset).toBe(550);
    const parsed = new URL(workspaceUrl(location), "https://example.test");
    expect(parseWorkbenchLocation("research", parsed.search)).toEqual(location);
  });
  it("opens the research workbench at intelligence search while keeping the user center explicit", () => {
    const researchHome = parseWorkbenchLocation("research");
    expect(researchHome.view).toBe("explorer");
    expect(workspaceUrl(researchHome)).toBe("/workspace/research?view=explorer");

    const userCenter = parseWorkbenchLocation("research", "?view=overview");
    expect(userCenter.view).toBe("overview");
    expect(workspaceUrl(userCenter)).toBe("/workspace/research?view=overview");
  });

  it("does not silently hide target projects with an active-only default", () => {
    const target = parseWorkbenchLocation(
      "research",
      "?view=target&entity=550E8400-E29B-41D4-A716-446655440000&section=pipeline",
    );

    expect(pipelineFiltersFromLocation(target, target.entityId ?? "")).toEqual(
      expect.objectContaining({ targetEntityId: target.entityId, programStatus: "" }),
    );
  });

  it("round-trips bounded search and entity deep links", () => {
    const explorer = parseWorkbenchLocation("research", "?view=explorer&q=%20EGFR%20");
    expect(explorer).toEqual({
      workbench: "research",
      view: "explorer",
      query: "EGFR",
      entityType: "",
      entityTypes: [],
      entityIncludeRelated: true,
      reviewStatus: "",
      entitySort: [{ field: "relevance", direction: "desc" }],
      entitySortBy: "relevance",
      entitySortDirection: "desc",
      explorerDisplayMode: "list",
      explorerAnalysisView: "chart",
      entityId: null,
      invalidEntityId: false,
      offset: 0,
    });
    expect(workspaceUrl(explorer)).toBe("/workspace/research?view=explorer&q=EGFR");

    const target = parseWorkbenchLocation(
      "research",
      "?view=target&q=EGFR&entity=550E8400-E29B-41D4-A716-446655440000&section=evidence",
    );
    expect(target.entityId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(target.query).toBe("EGFR");
    expect(target.targetSection).toBe("evidence");
    expect(workspaceUrl(target)).toBe(
      "/workspace/research?view=target&q=EGFR&entity=550e8400-e29b-41d4-a716-446655440000&section=evidence",
    );

    const drugReturnPath =
      "/workspace/research?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&section=relationships";
    const contextualTarget = parseWorkbenchLocation(
      "research",
      `?view=target&entity=550e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(drugReturnPath)}`,
    );
    expect(contextualTarget.returnTo).toBe(drugReturnPath);
    expect(workspaceUrl(contextualTarget)).toBe(
      `/workspace/research?view=target&entity=550e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(drugReturnPath)}`,
    );

    const trialReturnPath =
      "/workspace/research?view=target&entity=550e8400-e29b-41d4-a716-446655440000&section=trials";
    const contextualTrial = parseWorkbenchLocation(
      "research",
      `?view=trials&trial=770e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(trialReturnPath)}`,
    );
    expect(contextualTrial.returnTo).toBe(trialReturnPath);
    expect(workspaceUrl(contextualTrial)).toBe(
      `/workspace/research?view=trials&from=${encodeURIComponent(trialReturnPath)}&trial=770e8400-e29b-41d4-a716-446655440000`,
    );

    const trialDetailReturnPath = workspaceUrl(contextualTrial);
    const drugFromTrial = parseWorkbenchLocation(
      "research",
      `?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(trialDetailReturnPath)}`,
    );
    expect(drugFromTrial.returnTo).toBe(trialDetailReturnPath);
    expect(workspaceUrl(drugFromTrial)).toBe(
      `/workspace/research?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(trialDetailReturnPath)}`,
    );

    const pipelineReturnPath =
      "/workspace/research?view=pipeline&target_entity_id=550e8400-e29b-41d4-a716-446655440000&sort=status_date%3Adesc&offset=20";
    const canonicalPipelineReturnPath =
      "/workspace/research?view=pipeline&target_entity_id=550e8400-e29b-41d4-a716-446655440000&offset=20";
    const drugFromPipeline = parseWorkbenchLocation(
      "research",
      `?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(pipelineReturnPath)}`,
    );
    expect(drugFromPipeline.returnTo).toBe(canonicalPipelineReturnPath);
    expect(workspaceUrl(drugFromPipeline)).toBe(
      `/workspace/research?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(canonicalPipelineReturnPath)}`,
    );

    const drug = parseWorkbenchLocation(
      "research",
      "?view=drug&q=EGFR&entity=550E8400-E29B-41D4-A716-446655440000&section=pipeline&offset=100",
    );
    expect(drug.entityId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(drug.query).toBe("EGFR");
    expect(drug.drugSection).toBe("pipeline");
    expect(drug.offset).toBe(100);
    expect(workspaceUrl(drug)).toBe(
      "/workspace/research?view=drug&q=EGFR&entity=550e8400-e29b-41d4-a716-446655440000&section=pipeline&offset=100",
    );

    const targetReturnPath =
      "/workspace/research?view=target&entity=550e8400-e29b-41d4-a716-446655440000&section=pipeline&q=EGFR&phase=phase_3";
    const canonicalTargetReturnPath =
      "/workspace/research?view=target&q=EGFR&entity=550e8400-e29b-41d4-a716-446655440000&section=pipeline&phase=phase_3";
    const contextualDrug = parseWorkbenchLocation(
      "research",
      `?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(targetReturnPath)}`,
    );
    expect(contextualDrug.returnTo).toBe(canonicalTargetReturnPath);
    expect(workspaceUrl(contextualDrug)).toBe(
      `/workspace/research?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(canonicalTargetReturnPath)}`,
    );

    const comparisonReturnPath =
      "/workspace/research?view=collections&compare=880e8400-e29b-41d4-a716-446655440000,990e8400-e29b-41d4-a716-446655440000&collection=770e8400-e29b-41d4-a716-446655440000";
    const canonicalComparisonReturnPath =
      "/workspace/research?view=collections&collection=770e8400-e29b-41d4-a716-446655440000&compare=880e8400-e29b-41d4-a716-446655440000%2C990e8400-e29b-41d4-a716-446655440000";
    const comparisonDrug = parseWorkbenchLocation(
      "research",
      `?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(comparisonReturnPath)}`,
    );
    expect(comparisonDrug.returnTo).toBe(canonicalComparisonReturnPath);
    expect(workspaceUrl(comparisonDrug)).toBe(
      `/workspace/research?view=drug&entity=660e8400-e29b-41d4-a716-446655440000&from=${encodeURIComponent(canonicalComparisonReturnPath)}`,
    );

    const company = parseWorkbenchLocation(
      "research",
      "?view=company&entity=550E8400-E29B-41D4-A716-446655440000&section=timeline",
    );
    expect(company.entityId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(company.companySection).toBe("timeline");
    expect(workspaceUrl(company)).toBe(
      "/workspace/research?view=company&entity=550e8400-e29b-41d4-a716-446655440000&section=timeline",
    );

    const disease = parseWorkbenchLocation(
      "research",
      "?view=disease&entity=550E8400-E29B-41D4-A716-446655440000&section=epidemiology",
    );
    expect(disease.entityId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(disease.diseaseSection).toBe("epidemiology");
    expect(workspaceUrl(disease)).toBe(
      "/workspace/research?view=disease&entity=550e8400-e29b-41d4-a716-446655440000&section=epidemiology",
    );

    const entity = parseWorkbenchLocation(
      "research",
      "?view=entity&entity=550E8400-E29B-41D4-A716-446655440000&section=patents",
    );
    expect(entity.entityId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(entity.entitySection).toBe("patents");
    expect(workspaceUrl(entity)).toBe(
      "/workspace/research?view=entity&entity=550e8400-e29b-41d4-a716-446655440000&section=patents",
    );
  });

  it("fails closed for unknown views and malformed entity identifiers", () => {
    expect(parseWorkbenchLocation("research", "?view=internal-admin").view).toBe("explorer");
    expect(parseWorkbenchLocation("research", "?view=target&entity=../../secret")).toEqual({
      workbench: "research",
      view: "target",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: true,
      targetSection: "overview",
    });
    expect(parseWorkbenchLocation("research", "?view=entity&entity=not-a-uuid").invalidEntityId).toBe(true);
    expect(parseWorkbenchLocation("research", "?view=drug&entity=not-a-uuid").invalidEntityId).toBe(true);
    expect(parseWorkbenchLocation("research", "?view=company&entity=not-a-uuid").invalidEntityId).toBe(true);
    expect(parseWorkbenchLocation("research", "?view=disease&entity=not-a-uuid").invalidEntityId).toBe(true);
    expect(parseWorkbenchLocation("research", "?view=target&section=unknown").targetSection).toBe("overview");
    expect(parseWorkbenchLocation("research", "?view=drug&section=unknown").drugSection).toBe("overview");
    expect(parseWorkbenchLocation("research", "?view=company&section=unknown").companySection).toBe("overview");
    expect(parseWorkbenchLocation("research", "?view=disease&section=unknown").diseaseSection).toBe("overview");
    expect(parseWorkbenchLocation("research", "?view=entity&section=company_secrets").entitySection).toBe("overview");
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=drug&entity=550e8400-e29b-41d4-a716-446655440000&from=https%3A%2F%2Fevil.example%2Fworkspace%2Fresearch%3Fview%3Dtarget",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=drug&entity=550e8400-e29b-41d4-a716-446655440000&from=%2Fworkspace%2Fresearch%3Fview%3Dunknown%26q%3DEGFR",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=drug&entity=550e8400-e29b-41d4-a716-446655440000&from=%2Fworkspace%2Fresearch%3Fview%3Dcollections%26compare%3D660e8400-e29b-41d4-a716-446655440000",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=target&entity=550e8400-e29b-41d4-a716-446655440000&from=https%3A%2F%2Fevil.example%2Fworkspace%2Fresearch%3Fview%3Ddrug",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=target&entity=550e8400-e29b-41d4-a716-446655440000&from=%2Fworkspace%2Fresearch%3Fview%3Dfactory%26q%3DEGFR",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=trials&trial=770e8400-e29b-41d4-a716-446655440000&from=https%3A%2F%2Fevil.example%2Fworkspace%2Fresearch%3Fview%3Dtarget",
      ).returnTo,
    ).toBeUndefined();
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=trials&trial=770e8400-e29b-41d4-a716-446655440000&from=%2Fworkspace%2Fresearch%3Fview%3Denterprise%26q%3DEGFR",
      ).returnTo,
    ).toBeUndefined();
  });

  it("round-trips target dossier pipeline filters for shareable deep links", () => {
    const targetId = "550e8400-e29b-41d4-a716-446655440000";
    const target = parseWorkbenchLocation(
      "research",
      `?view=target&entity=${targetId}&section=pipeline&modality=antibody&modality=small%20molecule` +
        "&program_status=active&phase=phase_2&sort=phase%3Aasc&offset=100" +
        "&display=program&analysis_dimension=targets&analysis_view=table&analysis_top=50&analysis_stage=global&target_aggregation=primary",
    );

    expect(target).toMatchObject({
      view: "target",
      entityId: targetId,
      targetSection: "pipeline",
      pipelineModalities: ["antibody", "small molecule"],
      pipelineProgramStatus: "active",
      phase: "phase_2",
      pipelineSortBy: "phase",
      pipelineSortDirection: "asc",
      targetPipelineDisplayMode: "program",
      pipelineAnalysisDimension: "targets",
      pipelineAnalysisView: "table",
      pipelineAnalysisLimit: 50,
      pipelineAnalysisStageScope: "global",
      pipelineTargetAggregation: "primary",
      offset: 100,
    });
    const url = workspaceUrl(target);
    expect(url).toContain("view=target");
    expect(url).toContain("section=pipeline");
    expect(url).toContain("modality=antibody");
    expect(url).toContain("modality=small+molecule");
    expect(url).toContain("program_status=active");
    expect(url).toContain("sort=phase%3Aasc");
    expect(url).toContain("display=program");
    expect(url).toContain("analysis_dimension=targets");
    expect(url).toContain("analysis_view=table");
    expect(url).toContain("analysis_top=50");
    expect(url).toContain("analysis_stage=global");
    expect(url).toContain("target_aggregation=primary");
    expect(url).toContain("offset=100");
  });

  it("keeps the target pipeline active default distinct from an explicit all-projects choice", () => {
    const targetId = "550e8400-e29b-41d4-a716-446655440000";
    const defaultTarget = parseWorkbenchLocation("research", `?view=target&entity=${targetId}&section=pipeline`);
    expect(defaultTarget.pipelineProgramStatus).toBeUndefined();

    const allProjects = parseWorkbenchLocation(
      "research",
      `?view=target&entity=${targetId}&section=pipeline&program_status=all`,
    );
    expect(allProjects.pipelineProgramStatus).toBe("all");
    expect(workspaceUrl(allProjects)).toContain("program_status=all");
  });

  it("keeps chemistry saved-search links opaque and tenant-scoped", () => {
    const chemistry = parseWorkbenchLocation("research", "?view=chemistry&saved=550E8400-E29B-41D4-A716-446655440000");
    expect(chemistry.chemistrySavedSearchId).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(chemistry.invalidChemistrySavedSearchId).toBe(false);
    expect(workspaceUrl(chemistry)).toBe(
      "/workspace/research?view=chemistry&saved=550e8400-e29b-41d4-a716-446655440000",
    );

    const invalid = parseWorkbenchLocation("research", "?view=chemistry&saved=not-a-uuid");
    expect(invalid.chemistrySavedSearchId).toBeNull();
    expect(invalid.invalidChemistrySavedSearchId).toBe(true);
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=chemistry");
  });

  it("round-trips monitoring tabs and canonicalizes unknown tabs to alerts", () => {
    const savedSearches = parseWorkbenchLocation("research", "?view=monitoring&monitor_tab=searches");
    expect(savedSearches).toMatchObject({ view: "monitoring", monitoringTab: "searches" });
    expect(workspaceUrl(savedSearches)).toBe("/workspace/research?view=monitoring&monitor_tab=searches");

    const invalid = parseWorkbenchLocation("research", "?view=monitoring&monitor_tab=not-a-tab");
    expect(invalid.monitoringTab).toBe("alerts");
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=monitoring");
  });

  it("round-trips a bounded comparison collection and four ordered entity selections", () => {
    const collectionId = "550E8400-E29B-41D4-A716-446655440020";
    const comparedIds = [
      "550E8400-E29B-41D4-A716-446655440001",
      "550E8400-E29B-41D4-A716-446655440002",
      "550E8400-E29B-41D4-A716-446655440003",
      "550E8400-E29B-41D4-A716-446655440004",
      "550E8400-E29B-41D4-A716-446655440005",
    ];
    const location = parseWorkbenchLocation(
      "research",
      `?view=collections&collection=${collectionId}&compare=${comparedIds.join(",")}`,
    );
    expect(location).toMatchObject({
      view: "collections",
      collectionId: collectionId.toLowerCase(),
      invalidCollectionId: false,
      collectionCompareEntityIds: comparedIds.slice(0, 4).map((entityId) => entityId.toLowerCase()),
    });
    expect(workspaceUrl(location)).toBe(
      "/workspace/research?view=collections&collection=550e8400-e29b-41d4-a716-446655440020" +
        "&compare=550e8400-e29b-41d4-a716-446655440001%2C550e8400-e29b-41d4-a716-446655440002%2C" +
        "550e8400-e29b-41d4-a716-446655440003%2C550e8400-e29b-41d4-a716-446655440004",
    );

    const invalid = parseWorkbenchLocation(
      "research",
      "?view=collections&collection=..%2Fsecret&compare=550e8400-e29b-41d4-a716-446655440001",
    );
    expect(invalid).toMatchObject({
      collectionId: null,
      invalidCollectionId: true,
      collectionCompareEntityIds: [],
    });
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=collections");
  });

  it("canonicalizes legacy knowledge links to the public coverage panel", () => {
    const pageId = "550E8400-E29B-41D4-A716-446655440099";
    const location = parseWorkbenchLocation(
      "research",
      `?view=knowledge&q=%20EGFR%20&page=${pageId}&panel=governance&version=2`,
    );
    expect(location).toMatchObject({
      view: "knowledge",
      query: "EGFR",
      knowledgePageId: pageId.toLowerCase(),
      invalidKnowledgePageId: false,
      knowledgePanel: "coverage",
      knowledgeVersionNumber: 2,
    });
    expect(workspaceUrl(location)).toBe(
      "/workspace/research?view=knowledge&q=EGFR&page=550e8400-e29b-41d4-a716-446655440099&panel=coverage&version=2",
    );

    const invalid = parseWorkbenchLocation(
      "research",
      "?view=knowledge&page=..%2Fsecret&panel=governance&version=999999999",
    );
    expect(invalid).toMatchObject({
      knowledgePageId: null,
      invalidKnowledgePageId: true,
      knowledgePanel: "document",
      knowledgeVersionNumber: null,
    });
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=knowledge");
  });

  it("round-trips bounded evidence queries, domains and citation locators", () => {
    const location = parseWorkbenchLocation(
      "research",
      "?view=evidence&q=%20EGFR%20L858R%20&dataset=patents&dataset=literature&dataset=unknown&document=doc%3Aegfr-7&chunk=2",
    );
    expect(location).toMatchObject({
      view: "evidence",
      query: "EGFR L858R",
      evidenceDatasetKeys: ["literature", "patents", "unknown"],
      evidenceDocumentId: "doc:egfr-7",
      evidenceChunkIndex: 1,
    });
    expect(workspaceUrl(location)).toBe(
      "/workspace/research?view=evidence&q=EGFR+L858R&dataset=literature&dataset=patents&dataset=unknown&document=doc%3Aegfr-7&chunk=2",
    );

    const invalid = parseWorkbenchLocation(
      "research",
      "?view=evidence&q=x&dataset=unknown&document=bad%0Aid&chunk=999",
    );
    expect(invalid).toMatchObject({
      query: "",
      evidenceDatasetKeys: [],
      evidenceDocumentId: null,
      evidenceChunkIndex: null,
    });
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=evidence");
  });

  it("round-trips governed explorer filters and drops invalid values", () => {
    const governed = parseWorkbenchLocation(
      "research",
      "?view=explorer&type=target&review=verified&sort_by=updated_at&sort_direction=asc&offset=100",
    );
    expect(governed.entityType).toBe("target");
    expect(governed.entityTypes).toEqual(["target"]);
    expect(governed.reviewStatus).toBe("verified");
    expect(governed.entitySortBy).toBe("updated_at");
    expect(governed.entitySortDirection).toBe("asc");
    expect(governed.entitySort).toEqual([{ field: "updated_at", direction: "asc" }]);
    expect(governed.offset).toBe(100);
    expect(workspaceUrl(governed)).toBe(
      "/workspace/research?view=explorer&type=target&review=verified&sort=updated_at%3Aasc&offset=100",
    );
    const landscape = parseWorkbenchLocation(
      "research",
      "?view=explorer&q=EGFR&type=target&display=landscape&analysis_view=table",
    );
    expect(landscape).toMatchObject({ explorerDisplayMode: "landscape", explorerAnalysisView: "table" });
    expect(workspaceUrl(landscape)).toBe(
      "/workspace/research?view=explorer&q=EGFR&type=target&display=landscape&analysis_view=table",
    );
    const combined = parseWorkbenchLocation("research", "?view=explorer&types=target,drug,target,unknown");
    expect(combined.entityType).toBe("");
    expect(combined.entityTypes).toEqual(["target", "drug"]);
    expect(workspaceUrl(combined)).toBe("/workspace/research?view=explorer&types=target%2Cdrug");
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=explorer&review=not-a-status&sort_by=unknown&sort_direction=sideways&offset=-20",
      ),
    ).toMatchObject({
      reviewStatus: "",
      entitySortBy: "relevance",
      entitySortDirection: "desc",
      offset: 0,
    });
  });

  it("preserves ordered multi-sort state and fails closed for malformed lists", () => {
    const ordered = parseWorkbenchLocation(
      "research",
      "?view=explorer&sort=updated_at%3Adesc&sort=name%3Aasc&sort=entity_type%3Adesc",
    );
    expect(ordered.entitySort).toEqual([
      { field: "updated_at", direction: "desc" },
      { field: "name", direction: "asc" },
      { field: "entity_type", direction: "desc" },
    ]);
    expect(ordered.entitySortBy).toBe("updated_at");
    expect(ordered.entitySortDirection).toBe("desc");
    expect(workspaceUrl(ordered)).toBe(
      "/workspace/research?view=explorer&sort=updated_at%3Adesc&sort=name%3Aasc&sort=entity_type%3Adesc",
    );

    for (const invalid of [
      "?view=explorer&sort=name%3Aasc&sort=name%3Adesc",
      "?view=explorer&sort=unknown%3Aasc",
      "?view=explorer&sort=name%3Asideways",
      "?view=explorer&sort=name%3Aasc&sort=entity_type%3Aasc&sort=updated_at%3Aasc&sort=relevance%3Aasc&sort=name%3Adesc&sort=entity_type%3Adesc",
    ]) {
      const location = parseWorkbenchLocation("research", invalid);
      expect(location.entitySort).toEqual([{ field: "relevance", direction: "desc" }]);
      expect(workspaceUrl(location)).toBe("/workspace/research?view=explorer");
    }

    const unscopedDealAmount = parseWorkbenchLocation(
      "research",
      "?view=deals&sort=name%3Aasc&sort=upfront_amount%3Adesc",
    );
    expect(unscopedDealAmount.dealSort).toEqual([{ field: "announced_at", direction: "asc" }]);
    const scopedDealAmount = parseWorkbenchLocation(
      "research",
      "?view=deals&currency=USD&sort=name%3Aasc&sort=upfront_amount%3Adesc",
    );
    expect(scopedDealAmount.dealSort).toEqual([
      { field: "name", direction: "asc" },
      { field: "upfront_amount", direction: "desc" },
    ]);
  });

  it("round-trips an explorer quick-detail entity and rejects malformed identifiers", () => {
    const entityId = "550e8400-e29b-41d4-a716-446655440000";
    const detail = parseWorkbenchLocation(
      "research",
      `?view=explorer&q=EGFR&type=target&entity=${entityId}&offset=100`,
    );
    expect(detail).toMatchObject({
      view: "explorer",
      query: "EGFR",
      entityType: "target",
      entityId,
      invalidEntityId: false,
      offset: 100,
    });
    expect(workspaceUrl(detail)).toBe(
      `/workspace/research?view=explorer&q=EGFR&type=target&offset=100&entity=${entityId}`,
    );

    const invalid = parseWorkbenchLocation("research", "?view=explorer&q=EGFR&entity=../../secret");
    expect(invalid.entityId).toBeNull();
    expect(invalid.invalidEntityId).toBe(true);
    expect(workspaceUrl(invalid)).toBe("/workspace/research?view=explorer&q=EGFR");
  });

  it("round-trips bounded pipeline filters and pagination", () => {
    const drugId = "e5f40269-f4c3-4f52-a052-3d6f633e67af";
    const targetId = "c3f40269-f4c3-4f52-a052-3d6f633e67af";
    const combinationTargetId = "d4f40269-f4c3-4f52-a052-3d6f633e67af";
    const targetCombinationKey = `${targetId}|${combinationTargetId}`;
    const diseaseId = "b2f40269-f4c3-4f52-a052-3d6f633e67af";
    const organizationId = "a1f40269-f4c3-4f52-a052-3d6f633e67af";
    const pipeline = parseWorkbenchLocation(
      "research",
      "?view=pipeline&q=EGFR&modality=small%20molecule&program_status=active" +
        "&organization_role=collaborator&organization_type=biotech&organization_country_region=US" +
        "&phase=phase_2&geography=Global" +
        `&status_date_from=2026-01-01&status_date_to=2026-07-31&drug_entity_id=${drugId}` +
        `&target_entity_id=${targetId}` +
        `&target_combination_key=${targetCombinationKey}` +
        `&disease_entity_id=${diseaseId}&organization_entity_id=${organizationId}` +
        "&global_phase=phase_2&china_phase=phase_1&global_phase_started_from=2026-01-01" +
        "&global_phase_started_to=2026-07-31&china_phase_started_from=2025-01-01" +
        "&china_phase_started_to=2025-07-31&development_rights_region=Global" +
        "&commercialization_rights_region=Greater%20China&program_tag=first_in_class" +
        "&milestone_type=first_patient_in&milestone_from=2026-06-01&milestone_to=2026-06-30" +
        "&has_clinical_results=true&clinical_result_evaluation=positive&has_deal=true&deal_currency=USD" +
        "&deal_total_potential_amount_min=400000000&deal_total_potential_amount_max=600000000" +
        "&sort=mechanism_of_action%3Aasc&display=landscape" +
        "&analysis_dimension=targets&analysis_view=table&analysis_top=50" +
        "&analysis_stage=global&target_aggregation=primary&offset=100",
    );
    expect(pipeline).toMatchObject({
      view: "pipeline",
      query: "EGFR",
      pipelineModalities: ["small molecule"],
      pipelineProgramStatus: "active",
      pipelineOrganizationRole: "collaborator",
      pipelineOrganizationType: "biotech",
      pipelineOrganizationCountryRegion: "US",
      phase: "phase_2",
      geography: "Global",
      pipelineStatusDateFrom: "2026-01-01",
      pipelineStatusDateTo: "2026-07-31",
      pipelineDrugEntityId: drugId,
      pipelineTargetEntityId: targetId,
      pipelineTargetCombinationKey: targetCombinationKey,
      pipelineDiseaseEntityId: diseaseId,
      pipelineOrganizationEntityId: organizationId,
      pipelineGlobalPhase: "phase_2",
      pipelineChinaPhase: "phase_1",
      pipelineGlobalPhaseStartedFrom: "2026-01-01",
      pipelineGlobalPhaseStartedTo: "2026-07-31",
      pipelineChinaPhaseStartedFrom: "2025-01-01",
      pipelineChinaPhaseStartedTo: "2025-07-31",
      pipelineDevelopmentRightsRegion: "Global",
      pipelineCommercializationRightsRegion: "Greater China",
      pipelineProgramTags: ["first_in_class"],
      pipelineMilestoneType: "first_patient_in",
      pipelineMilestoneFrom: "2026-06-01",
      pipelineMilestoneTo: "2026-06-30",
      pipelineHasClinicalResults: "true",
      pipelineClinicalResultEvaluation: "positive",
      pipelineHasDeal: "true",
      pipelineDealCurrency: "USD",
      pipelineDealTotalPotentialAmountMin: "400000000",
      pipelineDealTotalPotentialAmountMax: "600000000",
      pipelineSortBy: "mechanism_of_action",
      pipelineSortDirection: "asc",
      pipelineDisplayMode: "landscape",
      pipelineAnalysisDimension: "targets",
      pipelineAnalysisView: "table",
      pipelineAnalysisLimit: 50,
      pipelineAnalysisStageScope: "global",
      pipelineTargetAggregation: "primary",
      offset: 100,
    });
    expect(workspaceUrl(pipeline)).toBe(
      "/workspace/research?view=pipeline&q=EGFR&modality=small+molecule&program_status=active" +
        "&organization_role=collaborator&organization_type=biotech&organization_country_region=US" +
        "&phase=phase_2&geography=Global" +
        `&status_date_from=2026-01-01&status_date_to=2026-07-31&drug_entity_id=${drugId}` +
        `&target_entity_id=${targetId}` +
        `&target_combination_key=${targetId}%7C${combinationTargetId}` +
        `&disease_entity_id=${diseaseId}&organization_entity_id=${organizationId}` +
        "&global_phase=phase_2&china_phase=phase_1&global_phase_started_from=2026-01-01" +
        "&global_phase_started_to=2026-07-31&china_phase_started_from=2025-01-01" +
        "&china_phase_started_to=2025-07-31&development_rights_region=Global" +
        "&commercialization_rights_region=Greater+China&program_tag=first_in_class" +
        "&milestone_type=first_patient_in&milestone_from=2026-06-01&milestone_to=2026-06-30" +
        "&has_clinical_results=true&clinical_result_evaluation=positive&has_deal=true&deal_currency=USD" +
        "&deal_total_potential_amount_min=400000000&deal_total_potential_amount_max=600000000" +
        "&sort=mechanism_of_action%3Aasc&display=landscape" +
        "&analysis_dimension=targets&analysis_view=table&analysis_top=50" +
        "&analysis_stage=global&target_aggregation=primary&offset=100",
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=pipeline&phase=invalid-phase&organization_role=partner&status_date_from=invalid&status_date_to=2026-02-30" +
          "&has_clinical_results=unknown&clinical_result_evaluation=unknown&has_deal=unknown" +
          "&deal_currency=usd&deal_total_potential_amount_min=-1&deal_total_potential_amount_max=nan" +
          "&analysis_dimension=unknown&analysis_view=unknown&analysis_top=999&offset=-20",
      ),
    ).toMatchObject({
      phase: "",
      pipelineOrganizationRole: "",
      pipelineStatusDateFrom: "",
      pipelineStatusDateTo: "",
      pipelineHasClinicalResults: "",
      pipelineClinicalResultEvaluation: "",
      pipelineHasDeal: "",
      pipelineDealCurrency: "",
      pipelineDealTotalPotentialAmountMin: "",
      pipelineDealTotalPotentialAmountMax: "",
      pipelineSortBy: "status_date",
      pipelineSortDirection: "desc",
      pipelineAnalysisDimension: "all",
      pipelineAnalysisView: "chart",
      pipelineAnalysisLimit: 8,
      pipelineAnalysisStageScope: "overall",
      pipelineTargetAggregation: "all",
      offset: 0,
    });
  });

  it("defaults a target-filtered pipeline to drug grain and round-trips an explicit project grain", () => {
    const targetId = "c3f40269-f4c3-4f52-a052-3d6f633e67af";
    const defaultTargetView = parseWorkbenchLocation("research", `?view=pipeline&target_entity_id=${targetId}`);
    expect(defaultTargetView.pipelineResultGrain).toBe("drug");
    expect(workspaceUrl(defaultTargetView)).toBe(`/workspace/research?view=pipeline&target_entity_id=${targetId}`);

    const projectView = parseWorkbenchLocation(
      "research",
      `?view=pipeline&target_entity_id=${targetId}&result_grain=program`,
    );
    expect(projectView.pipelineResultGrain).toBe("program");
    expect(workspaceUrl(projectView)).toBe(
      `/workspace/research?view=pipeline&target_entity_id=${targetId}&result_grain=program`,
    );
  });

  it("round-trips bounded clinical-trial filters without sharing pipeline phase state", () => {
    const trialId = "c3f40269-f4c3-4f52-a052-3d6f633e67af";
    const roleEntityId = "550e8400-e29b-41d4-a716-446655440003";
    const trials = parseWorkbenchLocation(
      "research",
      "?view=trials&q=EGFR&registry=ClinicalTrials.gov&status=RECRUITING&phase=PHASE2" +
        "&study_type=INTERVENTIONAL&acronym=KEYNOTE&initiation_type=ist&therapy_line=first_line" +
        "&has_results=true&result_evaluation=positive&results_posted_from=2026-01-01" +
        "&results_posted_to=2026-07-31&investigational_drug=VX-101&combination_drug=Pembrolizumab" +
        "&investigational_target=EGFR&combination_target=PD-1&linked_drug_modality=antibody" +
        "&linked_drug_modality=small%20molecule&linked_drug_innovation_type=innovative" +
        "&linked_drug_category=biologic&linked_drug_program_tag=first_in_class" +
        `&linked_drug_global_phase=phase_3&linked_drug_organization_country_region=CN&role_entity_id=${roleEntityId}` +
        "&role_entity_role=investigational_drug&has_key_result=true&publication_id=PMID%3A12345678" +
        `&conference=ASCO%202026&disclosed_from=2026-06-01&disclosed_to=2026-07-31&sort_by=registry_id` +
        `&sort_direction=asc&display=landscape&analysis_view=table&trial=${trialId}&section=outcomes&offset=100`,
    );
    expect(trials).toMatchObject({
      view: "trials",
      query: "EGFR",
      registry: "ClinicalTrials.gov",
      trialStatus: "RECRUITING",
      trialPhase: "PHASE2",
      studyType: "INTERVENTIONAL",
      trialAcronym: "KEYNOTE",
      trialInitiationType: "ist",
      trialTherapyLine: "first_line",
      trialHasResults: "true",
      trialResultEvaluation: "positive",
      trialResultsPostedFrom: "2026-01-01",
      trialResultsPostedTo: "2026-07-31",
      trialInvestigationalDrug: "VX-101",
      trialCombinationDrug: "Pembrolizumab",
      trialInvestigationalTarget: "EGFR",
      trialCombinationTarget: "PD-1",
      trialLinkedDrugModalities: ["antibody", "small molecule"],
      trialLinkedDrugInnovationTypes: ["innovative"],
      trialLinkedDrugCategories: ["biologic"],
      trialLinkedDrugProgramTags: ["first_in_class"],
      trialLinkedDrugGlobalPhase: "phase_3",
      trialLinkedDrugOrganizationCountryRegion: "CN",
      trialRoleEntityId: roleEntityId,
      trialRoleEntityRole: "investigational_drug",
      trialHasKeyResult: "true",
      trialPublicationId: "PMID:12345678",
      trialConference: "ASCO 2026",
      trialDisclosedFrom: "2026-06-01",
      trialDisclosedTo: "2026-07-31",
      trialSortBy: "registry_id",
      trialSortDirection: "asc",
      trialDisplayMode: "landscape",
      trialAnalysisView: "table",
      trialId,
      invalidTrialId: false,
      trialSection: "outcomes",
      offset: 100,
    });
    expect(workspaceUrl(trials)).toBe(
      "/workspace/research?view=trials&q=EGFR&registry=ClinicalTrials.gov&status=RECRUITING&phase=PHASE2" +
        "&study_type=INTERVENTIONAL&acronym=KEYNOTE&initiation_type=ist&therapy_line=first_line" +
        "&has_results=true&result_evaluation=positive&results_posted_from=2026-01-01" +
        "&results_posted_to=2026-07-31&investigational_drug=VX-101&combination_drug=Pembrolizumab" +
        "&investigational_target=EGFR&combination_target=PD-1&linked_drug_modality=antibody" +
        "&linked_drug_modality=small+molecule&linked_drug_innovation_type=innovative" +
        "&linked_drug_category=biologic&linked_drug_program_tag=first_in_class" +
        `&linked_drug_global_phase=phase_3&linked_drug_organization_country_region=CN&role_entity_id=${roleEntityId}` +
        "&role_entity_role=investigational_drug&has_key_result=true&publication_id=PMID%3A12345678" +
        `&conference=ASCO+2026&disclosed_from=2026-06-01&disclosed_to=2026-07-31&sort=registry_id%3Aasc` +
        `&display=landscape&analysis_view=table&trial=${trialId}&section=outcomes&offset=100`,
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=trials&has_results=unknown&result_evaluation=unknown&results_posted_from=invalid" +
          "&initiation_type=unknown&therapy_line=unknown" +
          "&results_posted_to=2026-02-30&has_key_result=unknown&disclosed_from=invalid&disclosed_to=2026-02-30" +
          "&role_entity_id=invalid&role_entity_role=investigational_drug" +
          "&linked_drug_global_phase=invalid-phase" +
          "&sort_by=unknown&sort_direction=sideways&trial=invalid&offset=-20",
      ),
    ).toMatchObject({
      trialPhase: "",
      trialHasResults: "",
      trialInitiationType: "",
      trialTherapyLine: "",
      trialResultEvaluation: "",
      trialResultsPostedFrom: "",
      trialResultsPostedTo: "",
      trialHasKeyResult: "",
      trialDisclosedFrom: "",
      trialDisclosedTo: "",
      trialRoleEntityId: "",
      trialRoleEntityRole: "",
      trialLinkedDrugGlobalPhase: "",
      trialSortBy: "last_update_posted",
      trialSortDirection: "desc",
      trialDisplayMode: "list",
      trialId: null,
      invalidTrialId: true,
      trialSection: "overview",
      offset: 0,
    });
    expect(parseWorkbenchLocation("research", `?view=trials&trial=${trialId}&section=unknown`).trialSection).toBe(
      "overview",
    );
  });

  it("canonicalizes repeated clinical role entities with OR semantics", () => {
    const firstId = "550e8400-e29b-41d4-a716-446655440003";
    const secondId = "550e8400-e29b-41d4-a716-446655440004";
    const location = parseWorkbenchLocation(
      "research",
      `?view=trials&role_entity_ids=${secondId}&role_entity_ids=${firstId}` +
        `&role_entity_ids=${secondId}&role_entity_role=investigational_drug`,
    );

    expect(location).toMatchObject({
      trialRoleEntityId: "",
      trialRoleEntityIds: [firstId, secondId],
      trialRoleEntityRole: "investigational_drug",
    });
    expect(workspaceUrl(location)).toContain(
      `role_entity_ids=${firstId}&role_entity_ids=${secondId}&role_entity_role=investigational_drug`,
    );
  });

  it("round-trips clinical role groups with OR within each group and AND across groups", () => {
    const drugA = "550e8400-e29b-41d4-a716-446655440010";
    const drugB = "550e8400-e29b-41d4-a716-446655440011";
    const combination = "550e8400-e29b-41d4-a716-446655440012";
    const target = "550e8400-e29b-41d4-a716-446655440013";
    const location = parseWorkbenchLocation(
      "research",
      `?view=trials&investigational_drug_entity_ids=${drugB}` +
        `&investigational_drug_entity_ids=${drugA}` +
        `&investigational_drug_entity_ids=${drugB}` +
        `&combination_drug_entity_ids=${combination}` +
        `&investigational_target_entity_ids=${target}`,
    );

    expect(location).toMatchObject({
      trialInvestigationalDrugEntityIds: [drugA, drugB],
      trialCombinationDrugEntityIds: [combination],
      trialInvestigationalTargetEntityIds: [target],
      trialCombinationTargetEntityIds: [],
    });
    expect(workspaceUrl(location)).toContain(
      `investigational_drug_entity_ids=${drugA}&investigational_drug_entity_ids=${drugB}` +
        `&combination_drug_entity_ids=${combination}&investigational_target_entity_ids=${target}`,
    );
  });

  it("round-trips bounded patent filters and pagination", () => {
    const patentId = "550e8400-e29b-41d4-a716-446655440020";
    const patents = parseWorkbenchLocation(
      "research",
      "?view=patents&q=EGFR&applicant=Victor%20Therapeutics&legal_status=ACTIVE" +
        `&sort_by=legal_status&sort_direction=asc&patent=${patentId}&section=relationships&offset=100`,
    );
    expect(patents).toMatchObject({
      view: "patents",
      query: "EGFR",
      applicant: "Victor Therapeutics",
      legalStatus: "ACTIVE",
      patentSortBy: "legal_status",
      patentSortDirection: "asc",
      patentId,
      invalidPatentId: false,
      patentSection: "relationships",
      offset: 100,
    });
    expect(workspaceUrl(patents)).toBe(
      "/workspace/research?view=patents&q=EGFR&applicant=Victor+Therapeutics&legal_status=ACTIVE" +
        `&sort=legal_status%3Aasc&patent=${patentId}&section=relationships&offset=100`,
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=patents&sort_by=unknown&sort_direction=sideways&patent=invalid&offset=-20",
      ),
    ).toMatchObject({
      applicant: "",
      legalStatus: "",
      patentSortBy: "priority_date",
      patentSortDirection: "desc",
      patentId: null,
      invalidPatentId: true,
      patentSection: "overview",
      offset: 0,
    });
    expect(parseWorkbenchLocation("research", `?view=patents&patent=${patentId}&section=unknown`).patentSection).toBe(
      "overview",
    );
  });

  it("round-trips bounded governed deal filters, detail and pagination", () => {
    const deals = parseWorkbenchLocation(
      "research",
      "?view=deals&q=VX-101&deal_type=license&status=active&direction=outbound" +
        "&direction_reference_jurisdiction=US&territory=global&party=Acme%20Pharma" +
        "&asset_entity_id=550e8400-e29b-41d4-a716-446655440004" +
        "&target_entity_id=550e8400-e29b-41d4-a716-446655440005" +
        "&disease_entity_id=550e8400-e29b-41d4-a716-446655440006" +
        "&asset_modality=antibody&asset_modality=small%20molecule" +
        "&asset_program_tag=first_in_class&asset_program_tag=best_in_class" +
        "&party_entity_id=550e8400-e29b-41d4-a716-446655440002&party_role=licensor" +
        "&party_country_region=US&party_organization_type=biopharma" +
        "&development_phase_at_transaction=phase_2&current_development_phase=phase_3" +
        "&right_type=commercialization" +
        "&rights_territory=Greater%20China&currency=USD&announced_from=2026-01-01" +
        "&announced_to=2026-01-31&terminated_from=2026-02-01&terminated_to=2026-02-28" +
        "&source_updated_from=2026-03-01&source_updated_to=2026-03-31" +
        "&upfront_amount_min=10000000&upfront_amount_max=30000000" +
        "&total_potential_amount_min=100000000&total_potential_amount_max=500000000" +
        "&sort_by=upfront_amount&sort_direction=asc&display=landscape" +
        "&analysis_dimension=party_country&analysis_view=table&analysis_top=20" +
        "&deal=550e8400-e29b-41d4-a716-446655440010&section=rights&offset=100",
    );
    expect(deals).toMatchObject({
      view: "deals",
      query: "VX-101",
      dealType: "license",
      dealStatus: "active",
      dealDirection: "outbound",
      dealDirectionReferenceJurisdiction: "US",
      dealTerritory: "global",
      dealAssetEntityId: "550e8400-e29b-41d4-a716-446655440004",
      dealTargetEntityId: "550e8400-e29b-41d4-a716-446655440005",
      dealDiseaseEntityId: "550e8400-e29b-41d4-a716-446655440006",
      dealAssetModalities: ["antibody", "small molecule"],
      dealAssetProgramTags: ["first_in_class", "best_in_class"],
      dealParty: "Acme Pharma",
      dealPartyEntityId: "550e8400-e29b-41d4-a716-446655440002",
      dealPartyRole: "licensor",
      dealPartyCountryRegion: "US",
      dealPartyOrganizationType: "biopharma",
      dealDevelopmentPhaseAtTransaction: "phase_2",
      dealCurrentDevelopmentPhase: "phase_3",
      dealRightType: "commercialization",
      dealRightsTerritory: "Greater China",
      dealCurrency: "USD",
      dealAnnouncedFrom: "2026-01-01",
      dealAnnouncedTo: "2026-01-31",
      dealTerminatedFrom: "2026-02-01",
      dealTerminatedTo: "2026-02-28",
      dealSourceUpdatedFrom: "2026-03-01",
      dealSourceUpdatedTo: "2026-03-31",
      dealUpfrontAmountMin: "10000000",
      dealUpfrontAmountMax: "30000000",
      dealTotalPotentialAmountMin: "100000000",
      dealTotalPotentialAmountMax: "500000000",
      dealSortBy: "upfront_amount",
      dealSortDirection: "asc",
      dealDisplayMode: "landscape",
      dealAnalysisDimension: "party_country",
      dealAnalysisView: "table",
      dealAnalysisLimit: 20,
      dealId: "550e8400-e29b-41d4-a716-446655440010",
      invalidDealId: false,
      dealSection: "rights",
      offset: 100,
    });
    expect(parseWorkbenchLocation("research", workspaceUrl(deals).split("?")[1])).toMatchObject(deals);
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=deals&status=invalid&direction=inbound&party_entity_id=invalid" +
          "&asset_entity_id=invalid&target_entity_id=invalid&disease_entity_id=invalid" +
          "&currency=usd&announced_from=2026-02-30&upfront_amount_min=-1" +
          "&sort_by=upfront_amount&sort_direction=asc&display=invalid" +
          "&analysis_dimension=invalid&analysis_view=invalid&analysis_top=7&deal=invalid&offset=-20",
      ),
    ).toMatchObject({
      dealType: "",
      dealStatus: "",
      dealDirection: "inbound",
      dealTerritory: "",
      dealAssetEntityId: "",
      dealTargetEntityId: "",
      dealDiseaseEntityId: "",
      dealAssetModalities: [],
      dealAssetProgramTags: [],
      dealParty: "",
      dealPartyEntityId: "",
      dealCurrency: "",
      dealSortBy: "announced_at",
      dealSortDirection: "asc",
      dealDisplayMode: "list",
      dealAnalysisDimension: "all",
      dealAnalysisView: "chart",
      dealAnalysisLimit: 8,
      dealAnnouncedFrom: "",
      dealUpfrontAmountMin: "",
      dealId: null,
      invalidDealId: true,
      dealSection: "overview",
      offset: 0,
    });
    expect(
      parseWorkbenchLocation("research", "?view=deals&deal=550e8400-e29b-41d4-a716-446655440010&section=unknown")
        .dealSection,
    ).toBe("overview");
  });

  it("round-trips bounded regulatory timeline filters and pagination", () => {
    const regulatory = parseWorkbenchLocation(
      "research",
      "?view=regulatory&q=VX-101&agency=FDA&jurisdiction=US&event_type=approval&status=approved" +
        "&designation_type=breakthrough_therapy&label_change_type=initial_label&boxed_warning=true" +
        "&safety_signal_type=adverse_event&safety_severity=serious&safety_status=confirmed" +
        "&decision_from=2026-01-01&decision_to=2026-02-28" +
        "&source_updated_from=2026-02-01&source_updated_to=2026-03-01" +
        "&sort=subject%3Aasc" +
        "&regulatory_event=550e8400-e29b-41d4-a716-446655440010" +
        "&compare=550e8400-e29b-41d4-a716-446655440010,550e8400-e29b-41d4-a716-446655440011&offset=100",
    );
    expect(regulatory).toMatchObject({
      view: "regulatory",
      query: "VX-101",
      regulatoryAgency: "FDA",
      regulatoryJurisdiction: "US",
      regulatoryEventType: "approval",
      regulatoryStatus: "approved",
      regulatoryDesignationType: "breakthrough_therapy",
      regulatoryLabelChangeType: "initial_label",
      regulatoryBoxedWarning: "true",
      regulatorySafetySignalType: "adverse_event",
      regulatorySafetySeverity: "serious",
      regulatorySafetyStatus: "confirmed",
      regulatoryDecisionFrom: "2026-01-01",
      regulatoryDecisionTo: "2026-02-28",
      regulatorySourceUpdatedFrom: "2026-02-01",
      regulatorySourceUpdatedTo: "2026-03-01",
      regulatorySortBy: "subject",
      regulatorySortDirection: "asc",
      regulatoryEventId: "550e8400-e29b-41d4-a716-446655440010",
      invalidRegulatoryEventId: false,
      regulatoryCompareIds: ["550e8400-e29b-41d4-a716-446655440010", "550e8400-e29b-41d4-a716-446655440011"],
      offset: 100,
    });
    expect(workspaceUrl(regulatory)).toBe(
      "/workspace/research?view=regulatory&q=VX-101&agency=FDA&jurisdiction=US&event_type=approval&status=approved" +
        "&designation_type=breakthrough_therapy&label_change_type=initial_label&boxed_warning=true" +
        "&safety_signal_type=adverse_event&safety_severity=serious&safety_status=confirmed" +
        "&decision_from=2026-01-01&decision_to=2026-02-28" +
        "&source_updated_from=2026-02-01&source_updated_to=2026-03-01" +
        "&sort=subject%3Aasc" +
        "&regulatory_event=550e8400-e29b-41d4-a716-446655440010" +
        "&compare=550e8400-e29b-41d4-a716-446655440010%2C550e8400-e29b-41d4-a716-446655440011&offset=100",
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=regulatory&designation_type=invalid&boxed_warning=unknown&decision_from=2026-02-30" +
          "&regulatory_event=invalid&compare=invalid&offset=-20",
      ),
    ).toMatchObject({
      regulatoryAgency: "",
      regulatoryJurisdiction: "",
      regulatoryEventType: "",
      regulatoryStatus: "",
      regulatoryDesignationType: "",
      regulatoryBoxedWarning: "",
      regulatoryDecisionFrom: "",
      regulatorySortBy: "decision_date",
      regulatorySortDirection: "desc",
      regulatoryEventId: null,
      invalidRegulatoryEventId: true,
      regulatoryCompareIds: [],
      offset: 0,
    });
  });

  it("round-trips bounded epidemiology dimensions, dates and pagination", () => {
    const diseaseId = "550e8400-e29b-41d4-a716-446655440001";
    const epidemiology = parseWorkbenchLocation(
      "research",
      `?view=epidemiology&q=NSCLC&disease_entity_id=${diseaseId}&measure=prevalence&geography=China&unit=patients` +
        "&patient_population_id=550e8400-e29b-41d4-a716-446655440003" +
        "&population_scope=adults&age_group=18%2B&sex=all" +
        "&period_start_from=2024-01-01&period_end_to=2025-12-31" +
        "&sort=value%3Aasc&offset=100",
    );
    expect(epidemiology).toMatchObject({
      view: "epidemiology",
      query: "NSCLC",
      epidemiologyDiseaseEntityId: diseaseId,
      epidemiologyMeasure: "prevalence",
      epidemiologyGeography: "China",
      epidemiologyUnit: "patients",
      epidemiologyPatientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
      epidemiologyPopulationScope: "adults",
      epidemiologyAgeGroup: "18+",
      epidemiologySex: "all",
      epidemiologyPeriodStartFrom: "2024-01-01",
      epidemiologyPeriodEndTo: "2025-12-31",
      epidemiologySortBy: "value",
      epidemiologySortDirection: "asc",
      offset: 100,
    });
    expect(workspaceUrl(epidemiology)).toBe(
      `/workspace/research?view=epidemiology&q=NSCLC&disease_entity_id=${diseaseId}&measure=prevalence&geography=China&unit=patients` +
        "&patient_population_id=550e8400-e29b-41d4-a716-446655440003" +
        "&population_scope=adults&age_group=18%2B&sex=all" +
        "&period_start_from=2024-01-01&period_end_to=2025-12-31" +
        "&sort=value%3Aasc&offset=100",
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=epidemiology&period_start_from=2025-99-99&period_end_to=invalid&offset=-20",
      ),
    ).toMatchObject({
      epidemiologyMeasure: "",
      epidemiologyGeography: "",
      epidemiologyPeriodStartFrom: "",
      epidemiologyPeriodEndTo: "",
      epidemiologySortBy: "period_end",
      epidemiologySortDirection: "desc",
      offset: 0,
    });
  });

  it("round-trips bounded news dimensions, dates and pagination", () => {
    const newsEventId = "550e8400-e29b-41d4-a716-446655440021";
    const news = parseWorkbenchLocation(
      "research",
      "?view=news&q=Compound%20A&event_type=corporate_announcement&publisher=Acme%20Pharma" +
        "&language=en&venue=ASCO%202026&published_from=2026-01-01&published_to=2026-12-31" +
        `&content_scope=research&display=timeline&sort_by=title&sort_direction=asc&news_event=${newsEventId}&offset=100`,
    );
    expect(news).toMatchObject({
      view: "news",
      query: "Compound A",
      newsEventType: "corporate_announcement",
      newsPublisher: "Acme Pharma",
      newsLanguage: "en",
      newsVenue: "ASCO 2026",
      newsPublishedFrom: "2026-01-01",
      newsPublishedTo: "2026-12-31",
      newsContentScope: "research",
      newsDisplayMode: "timeline",
      newsSortBy: "title",
      newsSortDirection: "asc",
      newsEventId,
      invalidNewsEventId: false,
      offset: 100,
    });
    expect(workspaceUrl(news)).toBe(
      "/workspace/research?view=news&q=Compound+A&event_type=corporate_announcement&publisher=Acme+Pharma" +
        "&language=en&venue=ASCO+2026&published_from=2026-01-01&published_to=2026-12-31" +
        `&content_scope=research&display=timeline&sort=title%3Aasc&news_event=${newsEventId}&offset=100`,
    );
    expect(
      parseWorkbenchLocation(
        "research",
        "?view=news&published_from=2026-99-99&published_to=invalid&sort_by=unknown" +
          "&sort_direction=sideways&news_event=invalid&offset=-20",
      ),
    ).toMatchObject({
      newsPublishedFrom: "",
      newsPublishedTo: "",
      newsContentScope: "",
      newsDisplayMode: "list",
      newsSortBy: "published_at",
      newsSortDirection: "desc",
      newsEventId: null,
      invalidNewsEventId: true,
      offset: 0,
    });
  });

  it("fails closed when a view belongs to the other workbench", () => {
    expect(parseWorkbenchLocation("internal", "?view=enterprise").workbench).toBe("internal");
    expect(parseWorkbenchLocation("internal", "?view=explorer")).toMatchObject({
      workbench: "internal",
      view: "factory",
    });
    expect(parseWorkbenchLocation("research", "?view=governance")).toMatchObject({
      workbench: "research",
      view: "explorer",
    });
  });

  it("matches the server role boundary for restricted workspaces", () => {
    expect(canAccessView("factory", "viewer")).toBe(false);
    expect(canAccessView("governance", "viewer")).toBe(false);
    expect(canAccessView("factory", "analyst")).toBe(true);
    expect(canAccessView("commercial", "analyst")).toBe(false);
    expect(canAccessView("commercial", "admin")).toBe(true);
    expect(canAccessView("enterprise", "analyst")).toBe(false);
    expect(canAccessView("enterprise", "admin")).toBe(true);
    expect(canAccessWorkbench("research", "viewer")).toBe(true);
    expect(canAccessWorkbench("internal", "viewer")).toBe(false);
    expect(canAccessWorkbench("internal", "analyst")).toBe(true);
  });
});
