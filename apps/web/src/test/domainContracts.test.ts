import { expect, it, vi } from "vitest";
import { addComparisonSetMembers } from "../lib/contracts/collections";
import { emptyDealSearchFilters, loadDealFacetCatalog, saveDealSearch, searchDeals } from "../lib/contracts/deals";
import { loadEntityDossier } from "../lib/contracts/entityDossier";
import {
  loadEpidemiologyFacetCatalog,
  saveEpidemiologySearch,
  searchEpidemiology,
} from "../lib/contracts/epidemiology";
import { listEvidenceDatasets, searchEvidence } from "../lib/contracts/evidence";
import {
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  listKnowledgePageVersions,
} from "../lib/contracts/knowledge";
import { updateSavedSearchMetadata } from "../lib/contracts/monitoring";
import { loadNewsFacetCatalog, savedNewsQuery, saveNewsSearch, searchNewsEvents } from "../lib/contracts/news";
import { loadPatentFacetCatalog, savePatentSearch } from "../lib/contracts/patents";
import {
  emptyPipelineSearchFilters,
  hasPipelineSearchFilter,
  loadPipelineFacetCatalog,
  savePipelineSearch,
  searchPipelines,
} from "../lib/contracts/pipeline";
import {
  emptyRegulatorySearchFilters,
  loadRegulatoryFacetCatalog,
  saveRegulatorySearch,
  searchRegulatoryEvents,
} from "../lib/contracts/regulatory";
import { loadTargetDossier } from "../lib/contracts/target";
import { saveClinicalTrialSearch, searchTrials } from "../lib/contracts/trials";

function json(payload: unknown): Response {
  return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
}

it("loads the current principal's licensed evidence dataset catalog", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      json([{ attribution: "Open literature", dataset_key: "pilot-literature", display_name: "Pilot literature" }]),
    );

  await expect(listEvidenceDatasets()).resolves.toEqual([
    { attribution: "Open literature", dataset_key: "pilot-literature", display_name: "Pilot literature" },
  ]);
  expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/evidence/datasets");
});

it("normalizes optional evidence fields at the generated-client boundary", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      chunks: [
        {
          content: "Cited text",
          dataset_id: "literature",
          document_id: "document-1",
          document_name: "Paper",
        },
      ],
      engine: "opensearch",
      license_scopes: [],
      query: "EGFR",
    }),
  );

  const result = await searchEvidence({ query: " EGFR ", datasetKeys: ["literature"] });

  expect(result.chunks[0]).toMatchObject({ metadata: {}, positions: [], similarity: null });
  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    query: "EGFR",
    dataset_keys: ["literature"],
    limit: 20,
  });
});

it("loads and cancels the target dossier through one bounded contract request", async () => {
  const signals: AbortSignal[] = [];
  let resolveStarted: () => void = () => {};
  const started = new Promise<void>((resolve) => {
    resolveStarted = resolve;
  });
  vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    const signal = init?.signal;
    if (!(signal instanceof AbortSignal)) throw new Error("Expected a request AbortSignal");
    signals.push(signal);
    resolveStarted();
    return new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  });
  const controller = new AbortController();

  const dossier = loadTargetDossier("target-1", controller.signal);
  await started;
  controller.abort();

  await expect(dossier).rejects.toBeDefined();
  expect(signals).toHaveLength(1);
  expect(signals.every((signal) => signal.aborted)).toBe(true);
  expect(String(vi.mocked(globalThis.fetch).mock.calls[0]?.[0])).toContain(
    "/api/v1/targets/target-1/dossier?limit=100",
  );
});

it("loads a bounded cross-domain dossier through one cancellable contract request", async () => {
  let resolveStarted: () => void = () => {};
  const started = new Promise<void>((resolve) => {
    resolveStarted = resolve;
  });
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((_input, init) => {
    const signal = init?.signal;
    if (!(signal instanceof AbortSignal)) throw new Error("Expected a request AbortSignal");
    resolveStarted();
    return new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  });
  const controller = new AbortController();

  const dossier = loadEntityDossier("drug-1", controller.signal);
  await started;
  controller.abort();

  await expect(dossier).rejects.toBeDefined();
  expect(fetchMock).toHaveBeenCalledOnce();
  expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/api/v1/entities/drug-1/dossier?limit=50");
  const requestSignal = fetchMock.mock.calls[0]?.[1]?.signal;
  expect(requestSignal).toBeInstanceOf(AbortSignal);
  expect(requestSignal?.aborted).toBe(true);
});

it("uses bounded generated contracts for knowledge coverage and version history", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({}));

  await getKnowledgePageCoverage("page-1");
  await listKnowledgePageVersions("page-1");
  await getKnowledgePageVersionDiff("page-1", 4);

  const urls = fetchMock.mock.calls.map((call) => new URL(String(call[0]), window.location.origin));
  expect(urls[0]?.pathname).toBe("/api/v1/knowledge/pages/page-1/coverage");
  expect(urls[1]?.pathname).toBe("/api/v1/knowledge/pages/page-1/versions");
  expect(urls[1]?.searchParams.get("limit")).toBe("50");
  expect(urls[2]?.pathname).toBe("/api/v1/knowledge/pages/page-1/versions/4/diff");
});

it("updates saved-search metadata through the versioned monitoring contract", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({}));

  await updateSavedSearchMetadata("saved-search-1", {
    name: "EGFR competitive landscape",
    description: "Quarterly competitor review",
  });

  const [input, init] = fetchMock.mock.calls[0] ?? [];
  expect(String(input)).toBe("/api/v1/monitoring/saved-searches/saved-search-1");
  expect(init?.method).toBe("PATCH");
  expect(JSON.parse(String(init?.body))).toEqual({
    name: "EGFR competitive landscape",
    description: "Quarterly competitor review",
  });
});

it("adds selected entities through the atomic comparison-set batch contract", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({}));

  await addComparisonSetMembers("set-1", {
    entity_ids: ["entity-1", "entity-2"],
    expected_version: 4,
  });

  const [input, init] = fetchMock.mock.calls[0] ?? [];
  expect(String(input)).toBe("/api/v1/comparison-sets/set-1/members/batch");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(String(init?.body))).toEqual({
    entity_ids: ["entity-1", "entity-2"],
    expected_version: 4,
  });
});

it("maps the governed research publication scope without changing the list contract", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      json({ items: [], total: 0, limit: 100, offset: 0, facets: {}, as_of: "2026-07-24T00:00:00Z", warnings: [] }),
    );

  const filters = {
    analysisView: "chart" as const,
    query: "EGFR",
    entityId: "",
    eventType: "",
    publisher: "",
    language: "",
    venue: "ASCO 2026",
    publishedFrom: "",
    publishedTo: "",
    contentScope: "research" as const,
    displayMode: "timeline" as const,
    sortBy: "event_type" as const,
    sortDirection: "desc" as const,
    sort: [
      { field: "event_type" as const, direction: "desc" as const },
      { field: "title" as const, direction: "asc" as const },
    ],
  };

  await searchNewsEvents(filters, 0);

  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/news-events");
  expect(requestUrl.searchParams.get("content_scope")).toBe("research");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["event_type:desc", "title:asc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();
  expect(requestUrl.searchParams.get("display")).toBeNull();
  expect(savedNewsQuery(filters)).toMatchObject({
    sort_by: "event_type",
    sort_direction: "desc",
    sort: ["event_type:desc", "title:asc"],
  });
});

it("maps governed clinical role and disclosure filters to inclusive UTC query parameters", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.clinical_trial.search.v10",
      sort_by: "registry_id",
      sort_direction: "asc",
      applied_filters: [],
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      facets: {},
      landscape: { total_trials: 0, publication_year_phase: [], phase_evaluation: [] },
      as_of: "2026-07-23T00:00:00Z",
      warnings: [],
    }),
  );

  await searchTrials(
    "EGFR",
    "",
    "",
    "",
    "",
    "KEYNOTE",
    "ist",
    "first_line",
    "true",
    "positive",
    "2026-01-01",
    "2026-07-31",
    "VX-101",
    "Pembrolizumab",
    "EGFR",
    "PD-1",
    ["550e8400-e29b-41d4-a716-446655440010"],
    ["550e8400-e29b-41d4-a716-446655440011"],
    ["550e8400-e29b-41d4-a716-446655440012"],
    ["550e8400-e29b-41d4-a716-446655440013"],
    ["antibody"],
    ["first_in_class"],
    ["biologic"],
    ["breakthrough"],
    "phase_2",
    "CN",
    "",
    ["550e8400-e29b-41d4-a716-446655440004", "550e8400-e29b-41d4-a716-446655440003"],
    "investigational_drug",
    "true",
    "PMID:12345678",
    "ASCO 2026",
    "2026-06-01",
    "2026-07-31",
    "registry_id",
    "asc",
    0,
  );

  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.searchParams.get("results_posted_from")).toBe("2026-01-01T00:00:00.000Z");
  expect(requestUrl.searchParams.get("results_posted_to")).toBe("2026-07-31T23:59:59.999Z");
  expect(requestUrl.searchParams.get("has_results")).toBe("true");
  expect(requestUrl.searchParams.get("result_evaluation")).toBe("positive");
  expect(requestUrl.searchParams.get("acronym")).toBe("KEYNOTE");
  expect(requestUrl.searchParams.get("initiation_type")).toBe("ist");
  expect(requestUrl.searchParams.get("therapy_line")).toBe("first_line");
  expect(requestUrl.searchParams.get("investigational_drug")).toBe("VX-101");
  expect(requestUrl.searchParams.get("combination_drug")).toBe("Pembrolizumab");
  expect(requestUrl.searchParams.get("investigational_target")).toBe("EGFR");
  expect(requestUrl.searchParams.get("combination_target")).toBe("PD-1");
  expect(requestUrl.searchParams.getAll("investigational_drug_entity_ids")).toEqual([
    "550e8400-e29b-41d4-a716-446655440010",
  ]);
  expect(requestUrl.searchParams.getAll("combination_drug_entity_ids")).toEqual([
    "550e8400-e29b-41d4-a716-446655440011",
  ]);
  expect(requestUrl.searchParams.getAll("investigational_target_entity_ids")).toEqual([
    "550e8400-e29b-41d4-a716-446655440012",
  ]);
  expect(requestUrl.searchParams.getAll("combination_target_entity_ids")).toEqual([
    "550e8400-e29b-41d4-a716-446655440013",
  ]);
  expect(requestUrl.searchParams.getAll("linked_drug_modality")).toEqual(["antibody"]);
  expect(requestUrl.searchParams.getAll("linked_drug_innovation_type")).toEqual(["first_in_class"]);
  expect(requestUrl.searchParams.getAll("linked_drug_category")).toEqual(["biologic"]);
  expect(requestUrl.searchParams.getAll("linked_drug_program_tag")).toEqual(["breakthrough"]);
  expect(requestUrl.searchParams.get("linked_drug_global_phase")).toBe("phase_2");
  expect(requestUrl.searchParams.get("linked_drug_organization_country_region")).toBe("CN");
  expect(requestUrl.searchParams.get("role_entity_id")).toBeNull();
  expect(requestUrl.searchParams.getAll("role_entity_ids")).toEqual([
    "550e8400-e29b-41d4-a716-446655440003",
    "550e8400-e29b-41d4-a716-446655440004",
  ]);
  expect(requestUrl.searchParams.get("role_entity_role")).toBe("investigational_drug");
  expect(requestUrl.searchParams.get("has_key_result")).toBe("true");
  expect(requestUrl.searchParams.get("publication_id")).toBe("PMID:12345678");
  expect(requestUrl.searchParams.get("conference")).toBe("ASCO 2026");
  expect(requestUrl.searchParams.get("disclosed_from")).toBe("2026-06-01T00:00:00.000Z");
  expect(requestUrl.searchParams.get("disclosed_to")).toBe("2026-07-31T23:59:59.999Z");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["registry_id:asc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();
});

it("maps regional pipeline, rights and milestone filters to one governed request", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.pipeline.search.v13",
      sort_by: "status_date",
      sort_direction: "desc",
      applied_filters: [],
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      facets: {},
      as_of: "2026-07-24T00:00:00Z",
      warnings: [],
    }),
  );

  await searchPipelines(
    {
      ...emptyPipelineSearchFilters(),
      query: " VX-101 ",
      drugEntityId: "550e8400-e29b-41d4-a716-446655440004",
      targetEntityId: "550e8400-e29b-41d4-a716-446655440000",
      targetCombinationKey: "550e8400-e29b-41d4-a716-446655440000|550e8400-e29b-41d4-a716-446655440003",
      diseaseEntityId: "550e8400-e29b-41d4-a716-446655440001",
      organizationEntityId: "550e8400-e29b-41d4-a716-446655440002",
      organizationRole: "collaborator",
      organizationType: "biotech",
      organizationCountryRegion: "US",
      globalPhase: "phase_2",
      chinaPhase: "phase_1",
      developmentRightsRegion: "Global",
      commercializationRightsRegion: "Greater China",
      modalities: ["small molecule", "antibody"],
      programTags: ["first_in_class", "new_modality"],
      milestoneType: "first_patient_in",
      milestoneFrom: "2026-06-01",
      milestoneTo: "2026-06-30",
      hasClinicalResults: "true",
      clinicalResultEvaluation: "positive",
      hasDeal: "true",
      dealCurrency: "USD",
      dealTotalPotentialAmountMin: "400000000",
      dealTotalPotentialAmountMax: "600000000",
      sortBy: "drug_name",
      sortDirection: "asc",
    },
    { limit: 50, stageScope: "global", targetAggregation: "primary" },
  );

  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/pipelines");
  expect(requestUrl.searchParams.get("q")).toBe("VX-101");
  expect(requestUrl.searchParams.get("drug_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440004");
  expect(requestUrl.searchParams.get("target_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440000");
  expect(requestUrl.searchParams.get("target_combination_key")).toBe(
    "550e8400-e29b-41d4-a716-446655440000|550e8400-e29b-41d4-a716-446655440003",
  );
  expect(requestUrl.searchParams.get("disease_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440001");
  expect(requestUrl.searchParams.get("organization_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440002");
  expect(requestUrl.searchParams.get("organization_role")).toBe("collaborator");
  expect(requestUrl.searchParams.get("organization_type")).toBe("biotech");
  expect(requestUrl.searchParams.get("organization_country_region")).toBe("US");
  expect(requestUrl.searchParams.get("global_phase")).toBe("phase_2");
  expect(requestUrl.searchParams.get("china_phase")).toBe("phase_1");
  expect(requestUrl.searchParams.get("development_rights_region")).toBe("Global");
  expect(requestUrl.searchParams.get("commercialization_rights_region")).toBe("Greater China");
  expect(requestUrl.searchParams.getAll("modality")).toEqual(["small molecule", "antibody"]);
  expect(requestUrl.searchParams.getAll("program_tag")).toEqual(["first_in_class", "new_modality"]);
  expect(requestUrl.searchParams.get("milestone_type")).toBe("first_patient_in");
  expect(requestUrl.searchParams.get("milestone_from")).toBe("2026-06-01T00:00:00.000Z");
  expect(requestUrl.searchParams.get("milestone_to")).toBe("2026-06-30T23:59:59.999Z");
  expect(requestUrl.searchParams.get("has_clinical_results")).toBe("true");
  expect(requestUrl.searchParams.get("clinical_result_evaluation")).toBe("positive");
  expect(requestUrl.searchParams.get("has_deal")).toBe("true");
  expect(requestUrl.searchParams.get("deal_currency")).toBe("USD");
  expect(requestUrl.searchParams.get("deal_total_potential_amount_min")).toBe("400000000");
  expect(requestUrl.searchParams.get("deal_total_potential_amount_max")).toBe("600000000");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["drug_name:asc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();
  expect(requestUrl.searchParams.get("limit")).toBe("20");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.get("landscape_limit")).toBe("50");
  expect(requestUrl.searchParams.get("landscape_stage_scope")).toBe("global");
  expect(requestUrl.searchParams.get("landscape_target_aggregation")).toBe("primary");
});

it("loads a bounded authoritative pipeline facet catalog for the global professional query", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.pipeline.search.v13",
      sort_by: "status_date",
      sort_direction: "desc",
      items: [],
      total: 2,
      limit: 1,
      offset: 0,
      facets: {
        modality: { antibody: 1, "small molecule": 1 },
        program_tag: { first_in_class: 1, best_in_class: 1 },
      },
      landscape: {
        total_programs: 2,
        total_drugs: 2,
        total_targets: 2,
        total_diseases: 2,
        total_organizations: 2,
        dimensions: {},
      },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadPipelineFacetCatalog()).resolves.toMatchObject({
    facets: {
      modality: { antibody: 1, "small molecule": 1 },
      program_tag: { first_in_class: 1, best_in_class: 1 },
    },
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/pipelines");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["status_date:desc"]);
});

it("loads a bounded authoritative patent facet catalog for the global professional query", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.patent.search.v4",
      sort_by: "priority_date",
      sort_direction: "desc",
      items: [],
      total: 13,
      limit: 1,
      offset: 0,
      facets: {
        legal_status: { ACTIVE: 8, GRANTED: 5 },
        applicant: { "Victor Therapeutics": 4 },
      },
      landscape: {
        total_families: 13,
        dimensions: {},
      },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadPatentFacetCatalog()).resolves.toEqual({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      legal_status: { ACTIVE: 8, GRANTED: 5 },
      applicant: { "Victor Therapeutics": 4 },
    },
    warnings: [],
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/patent-families");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["priority_date:desc"]);
});

it("loads a bounded authoritative deal facet catalog for the global professional query", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.deal.search.v8",
      items: [],
      total: 9,
      limit: 1,
      offset: 0,
      facets: {
        deal_type: { license: 6 },
        direction: { outbound: 4 },
        currency: { USD: 7 },
      },
      landscape: { total_deals: 9, limit: 5 },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadDealFacetCatalog()).resolves.toEqual({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      deal_type: { license: 6 },
      direction: { outbound: 4 },
      currency: { USD: 7 },
    },
    warnings: [],
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/deal-transactions");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.get("analysis_top")).toBe("5");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["announced_at:desc"]);
});

it("loads a bounded authoritative regulatory facet catalog for the global professional query", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.regulatory.search.v4",
      items: [],
      total: 8,
      limit: 1,
      offset: 0,
      facets: {
        agency: { FDA: 8 },
        event_type: { approval: 8 },
        safety_status: { confirmed: 4 },
      },
      landscape: { total_events: 8 },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadRegulatoryFacetCatalog()).resolves.toEqual({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      agency: { FDA: 8 },
      event_type: { approval: 8 },
      safety_status: { confirmed: 4 },
    },
    warnings: [],
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/regulatory-event-timeline");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["decision_date:desc"]);
});

it("loads a bounded authoritative epidemiology facet and patient-population catalog", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.epidemiology.search.v3",
      applied_filters: [],
      items: [],
      total: 8,
      limit: 1,
      offset: 0,
      sort_by: "period_end",
      sort_direction: "desc",
      facets: {
        measure: { prevalence: 8 },
        geography: { China: 8 },
        unit: { patients: 8 },
        population_scope: { adults: 8 },
        age_group: { "18+": 8 },
        sex: { all: 8 },
      },
      patient_populations: [{ id: "550e8400-e29b-41d4-a716-446655440003", name: "EGFR positive adults", count: 8 }],
      landscape: { total_observations: 8, dimensions: {} },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadEpidemiologyFacetCatalog()).resolves.toEqual({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      measure: { prevalence: 8 },
      geography: { China: 8 },
      unit: { patients: 8 },
      population_scope: { adults: 8 },
      age_group: { "18+": 8 },
      sex: { all: 8 },
    },
    patient_populations: [{ id: "550e8400-e29b-41d4-a716-446655440003", name: "EGFR positive adults", count: 8 }],
    warnings: [],
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/epidemiology-observations");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["period_end:desc"]);
});

it("loads a bounded authoritative news and conference facet catalog", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.news.search.v3",
      applied_filters: [],
      items: [],
      total: 7,
      limit: 1,
      offset: 0,
      sort_by: "published_at",
      sort_direction: "desc",
      facets: {
        event_type: { conference_abstract: 7 },
        publisher: { ASCO: 7 },
        language: { en: 7 },
        venue: { "ASCO 2026": 7 },
      },
      landscape: { total_events: 7, event_type: [], venue: [], published_year: [] },
      as_of: "2026-07-30T00:00:00Z",
      warnings: [],
    }),
  );

  await expect(loadNewsFacetCatalog()).resolves.toEqual({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      event_type: { conference_abstract: 7 },
      publisher: { ASCO: 7 },
      language: { en: 7 },
      venue: { "ASCO 2026": 7 },
    },
    warnings: [],
  });
  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/news-events");
  expect(requestUrl.searchParams.get("limit")).toBe("1");
  expect(requestUrl.searchParams.get("offset")).toBe("0");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["published_at:desc"]);
});

it("saves and subscribes a typed professional pipeline query", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      json({
        id: "saved-pipeline",
        owner_user_id: "user-1",
        name: "EGFR global",
        description: "",
        query_type: "pipeline_search",
        query_version: 1,
        query_json: {},
        visibility: "private",
        created_at: "2026-07-26T00:00:00Z",
        updated_at: "2026-07-26T00:00:00Z",
      }),
    )
    .mockResolvedValueOnce(json({ id: "topic-1" }));

  const result = await savePipelineSearch({
    name: "EGFR global",
    filters: {
      ...emptyPipelineSearchFilters(),
      query: "EGFR",
      globalPhase: "phase_2",
      organizationRole: "licensee",
      organizationType: "biopharma",
      organizationCountryRegion: "CN",
      hasClinicalResults: "true",
      clinicalResultEvaluation: "positive",
      hasDeal: "true",
      dealCurrency: "USD",
      dealTotalPotentialAmountMin: "400000000",
    },
    analysis: {
      dimension: "targets",
      view: "table",
      limit: 50,
      stageScope: "global",
      targetAggregation: "primary",
    },
    displayMode: "landscape",
    shared: false,
    monitor: true,
  });

  const savedRequest = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
  expect(savedRequest).toMatchObject({
    name: "EGFR global",
    query_type: "pipeline_search",
    visibility: "private",
    query: {
      q: "EGFR",
      global_phase: "phase_2",
      organization_role: "licensee",
      organization_type: "biopharma",
      organization_country_region: "CN",
      has_clinical_results: true,
      clinical_result_evaluation: "positive",
      has_deal: true,
      deal_currency: "USD",
      deal_total_potential_amount_min: 400000000,
      display_mode: "landscape",
      analysis_dimension: "targets",
      analysis_view: "table",
      analysis_limit: 50,
      analysis_stage_scope: "global",
      target_aggregation: "primary",
    },
  });
  expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
    name: "EGFR global",
    saved_search_id: "saved-pipeline",
  });
  expect(result).toEqual({ kind: "saved", monitoring: true });
});

it("saves and subscribes a complete typed clinical trial query", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      json({
        id: "saved-trials",
        owner_user_id: "user-1",
        name: "EGFR trial results",
        description: "",
        query_type: "clinical_trial_search",
        query_version: 1,
        query_json: {},
        visibility: "tenant",
        created_at: "2026-07-26T00:00:00Z",
        updated_at: "2026-07-26T00:00:00Z",
      }),
    )
    .mockResolvedValueOnce(json({ id: "topic-trials" }));

  const result = await saveClinicalTrialSearch({
    name: "EGFR trial results",
    input: {
      query: "EGFR",
      registry: "ClinicalTrials.gov",
      status: "RECRUITING",
      phase: "PHASE2",
      studyType: "INTERVENTIONAL",
      acronym: "KEYNOTE",
      initiationType: "ist",
      therapyLine: "first_line",
      hasResults: "true",
      resultEvaluation: "positive",
      resultsPostedFrom: "2026-07-01",
      resultsPostedTo: "2026-07-31",
      investigationalDrug: "VX-101",
      combinationDrug: "Pembrolizumab",
      investigationalTarget: "EGFR",
      combinationTarget: "PD-1",
      investigationalDrugEntityIds: ["550e8400-e29b-41d4-a716-446655440010"],
      combinationDrugEntityIds: ["550e8400-e29b-41d4-a716-446655440011"],
      investigationalTargetEntityIds: ["550e8400-e29b-41d4-a716-446655440012"],
      combinationTargetEntityIds: ["550e8400-e29b-41d4-a716-446655440013"],
      linkedDrugModalities: ["antibody"],
      linkedDrugInnovationTypes: ["first_in_class"],
      linkedDrugCategories: ["biologic"],
      linkedDrugProgramTags: ["breakthrough"],
      linkedDrugGlobalPhase: "phase_2",
      linkedDrugOrganizationCountryRegion: "CN",
      roleEntityId: "",
      roleEntityIds: ["550e8400-e29b-41d4-a716-446655440004", "550e8400-e29b-41d4-a716-446655440003"],
      roleEntityRole: "investigational_drug",
      hasKeyResult: "true",
      publicationId: "PMID:12345678",
      conference: "ASCO",
      disclosedFrom: "2026-07-01",
      disclosedTo: "2026-07-31",
      sortBy: "result_evaluation",
      sortDirection: "asc",
      displayMode: "landscape" as const,
      analysisView: "table" as const,
    },
    shared: true,
    monitor: true,
  });

  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    name: "EGFR trial results",
    query_type: "clinical_trial_search",
    visibility: "tenant",
    query: {
      q: "EGFR",
      registry: "ClinicalTrials.gov",
      status: "RECRUITING",
      phase: "PHASE2",
      study_type: "INTERVENTIONAL",
      acronym: "KEYNOTE",
      initiation_type: "ist",
      therapy_line: "first_line",
      has_results: true,
      result_evaluation: "positive",
      results_posted_from: "2026-07-01",
      results_posted_to: "2026-07-31",
      investigational_drug: "VX-101",
      combination_drug: "Pembrolizumab",
      investigational_target: "EGFR",
      combination_target: "PD-1",
      investigational_drug_entity_ids: ["550e8400-e29b-41d4-a716-446655440010"],
      combination_drug_entity_ids: ["550e8400-e29b-41d4-a716-446655440011"],
      investigational_target_entity_ids: ["550e8400-e29b-41d4-a716-446655440012"],
      combination_target_entity_ids: ["550e8400-e29b-41d4-a716-446655440013"],
      linked_drug_modality: ["antibody"],
      linked_drug_innovation_type: ["first_in_class"],
      linked_drug_category: ["biologic"],
      linked_drug_program_tag: ["breakthrough"],
      linked_drug_global_phase: "phase_2",
      linked_drug_organization_country_region: "CN",
      role_entity_ids: ["550e8400-e29b-41d4-a716-446655440003", "550e8400-e29b-41d4-a716-446655440004"],
      role_entity_role: "investigational_drug",
      has_key_result: true,
      publication_id: "PMID:12345678",
      conference: "ASCO",
      disclosed_from: "2026-07-01",
      disclosed_to: "2026-07-31",
      sort: ["result_evaluation:asc"],
      sort_by: "result_evaluation",
      sort_direction: "asc",
      display_mode: "landscape",
      analysis_view: "table",
    },
  });
  expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
    name: "EGFR trial results",
    saved_search_id: "saved-trials",
  });
  expect(result).toEqual({ kind: "saved", monitoring: true });
});

it("maps governed deal role, stage, rights, time and amount filters to the generated client", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "pharma.deal.search.v8",
      applied_filters: [],
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      facets: {},
      landscape: { total_deals: 0, limit: 20 },
      as_of: "2026-07-24T00:00:00Z",
      warnings: [],
    }),
  );

  await searchDeals(
    {
      ...emptyDealSearchFilters,
      query: "VX-101",
      dealType: "license",
      status: "active",
      direction: "outbound",
      directionReferenceJurisdiction: "US",
      assetEntityId: "550e8400-e29b-41d4-a716-446655440004",
      targetEntityId: "550e8400-e29b-41d4-a716-446655440005",
      diseaseEntityId: "550e8400-e29b-41d4-a716-446655440006",
      assetModalities: ["antibody", "small molecule"],
      assetProgramTags: ["first_in_class", "best_in_class"],
      party: "Acme Pharma",
      partyEntityId: "550e8400-e29b-41d4-a716-446655440002",
      partyRole: "licensor",
      partyCountryRegion: "US",
      partyOrganizationType: "biopharma",
      developmentPhaseAtTransaction: "phase_2",
      currentDevelopmentPhase: "phase_3",
      rightType: "commercialization",
      rightsTerritory: "Greater China",
      currency: "USD",
      announcedFrom: "2026-01-01",
      announcedTo: "2026-01-31",
      terminatedFrom: "2026-02-01",
      terminatedTo: "2026-02-28",
      sourceUpdatedFrom: "2026-03-01",
      sourceUpdatedTo: "2026-03-31",
      upfrontAmountMin: "10000000",
      upfrontAmountMax: "30000000",
      totalPotentialAmountMin: "100000000",
      totalPotentialAmountMax: "500000000",
      sortBy: "upfront_amount",
      sortDirection: "asc",
    },
    100,
    20,
  );

  const requestUrl = new URL(String(fetchMock.mock.calls[0]?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/deal-transactions");
  expect(requestUrl.searchParams.get("asset_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440004");
  expect(requestUrl.searchParams.get("target_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440005");
  expect(requestUrl.searchParams.get("disease_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440006");
  expect(requestUrl.searchParams.getAll("asset_modality")).toEqual(["antibody", "small molecule"]);
  expect(requestUrl.searchParams.getAll("asset_program_tag")).toEqual(["first_in_class", "best_in_class"]);
  expect(requestUrl.searchParams.get("party_entity_id")).toBe("550e8400-e29b-41d4-a716-446655440002");
  expect(requestUrl.searchParams.get("party_role")).toBe("licensor");
  expect(requestUrl.searchParams.get("party_country_region")).toBe("US");
  expect(requestUrl.searchParams.get("party_organization_type")).toBe("biopharma");
  expect(requestUrl.searchParams.get("party")).toBeNull();
  expect(requestUrl.searchParams.get("development_phase_at_transaction")).toBe("phase_2");
  expect(requestUrl.searchParams.get("current_development_phase")).toBe("phase_3");
  expect(requestUrl.searchParams.get("right_type")).toBe("commercialization");
  expect(requestUrl.searchParams.get("rights_territory")).toBe("Greater China");
  expect(requestUrl.searchParams.get("announced_from")).toBe("2026-01-01T00:00:00.000Z");
  expect(requestUrl.searchParams.get("announced_to")).toBe("2026-01-31T23:59:59.999Z");
  expect(requestUrl.searchParams.get("terminated_from")).toBe("2026-02-01T00:00:00.000Z");
  expect(requestUrl.searchParams.get("source_updated_to")).toBe("2026-03-31T23:59:59.999Z");
  expect(requestUrl.searchParams.get("upfront_amount_min")).toBe("10000000");
  expect(requestUrl.searchParams.get("total_potential_amount_max")).toBe("500000000");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["upfront_amount:asc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();
  expect(requestUrl.searchParams.get("offset")).toBe("100");
  expect(requestUrl.searchParams.get("analysis_top")).toBe("20");
});

it("saves complete patent and deal queries through typed monitoring contracts", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ id: "saved-patent" }))
    .mockResolvedValueOnce(json({ id: "topic-patent" }))
    .mockResolvedValueOnce(json({ id: "saved-deal" }))
    .mockResolvedValueOnce(json({ id: "topic-deal" }));

  await savePatentSearch({
    name: "Active patents",
    input: {
      query: "EGFR",
      entityId: "",
      applicant: "Victor Therapeutics",
      legalStatus: "ACTIVE",
      priorityFrom: "",
      priorityTo: "",
      expirationFrom: "",
      expirationTo: "",
      sortBy: "family_identifier",
      sortDirection: "asc",
      displayMode: "landscape" as const,
      analysisView: "table" as const,
    },
    shared: true,
    monitor: true,
  });
  await saveDealSearch({
    name: "Outbound licenses",
    displayMode: "landscape",
    analysis: { dimension: "party_country", view: "table", limit: 20 },
    filters: {
      ...emptyDealSearchFilters,
      dealType: "license",
      status: "active",
      direction: "outbound",
      directionReferenceJurisdiction: "US",
      territory: "Greater China",
      assetEntityId: "550e8400-e29b-41d4-a716-446655440004",
      targetEntityId: "550e8400-e29b-41d4-a716-446655440005",
      diseaseEntityId: "550e8400-e29b-41d4-a716-446655440006",
      assetModalities: ["antibody", "small molecule"],
      assetProgramTags: ["first_in_class", "best_in_class"],
      party: "Acme Pharma",
      partyEntityId: "550e8400-e29b-41d4-a716-446655440002",
      partyRole: "licensor",
      partyCountryRegion: "US",
      partyOrganizationType: "biopharma",
      developmentPhaseAtTransaction: "phase_2",
      currentDevelopmentPhase: "phase_3",
      rightType: "commercialization",
      rightsTerritory: "Greater China",
      currency: "USD",
      announcedFrom: "2026-01-01",
      announcedTo: "2026-01-31",
      terminatedFrom: "2026-02-01",
      terminatedTo: "2026-02-28",
      sourceUpdatedFrom: "2026-03-01",
      sourceUpdatedTo: "2026-03-31",
      upfrontAmountMin: "10000000",
      upfrontAmountMax: "30000000",
      totalPotentialAmountMin: "100000000",
      totalPotentialAmountMax: "500000000",
      sortBy: "upfront_amount",
      sortDirection: "asc",
    },
    shared: false,
    monitor: true,
  });

  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    name: "Active patents",
    query_type: "patent_search",
    query: {
      q: "EGFR",
      applicant: "Victor Therapeutics",
      legal_status: "ACTIVE",
      sort: ["family_identifier:asc"],
      sort_by: "family_identifier",
      sort_direction: "asc",
      display_mode: "landscape",
      analysis_view: "table",
    },
    visibility: "tenant",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toMatchObject({
    name: "Outbound licenses",
    query_type: "deal_search",
    query: {
      deal_type: "license",
      status: "active",
      direction: "outbound",
      direction_reference_jurisdiction: "US",
      territory: "Greater China",
      asset_entity_id: "550e8400-e29b-41d4-a716-446655440004",
      target_entity_id: "550e8400-e29b-41d4-a716-446655440005",
      disease_entity_id: "550e8400-e29b-41d4-a716-446655440006",
      asset_modality: ["antibody", "small molecule"],
      asset_program_tag: ["first_in_class", "best_in_class"],
      party_entity_id: "550e8400-e29b-41d4-a716-446655440002",
      party_role: "licensor",
      party_country_region: "US",
      party_organization_type: "biopharma",
      development_phase_at_transaction: "phase_2",
      current_development_phase: "phase_3",
      right_type: "commercialization",
      rights_territory: "Greater China",
      currency: "USD",
      announced_from: "2026-01-01",
      announced_to: "2026-01-31",
      terminated_from: "2026-02-01",
      terminated_to: "2026-02-28",
      source_updated_from: "2026-03-01",
      source_updated_to: "2026-03-31",
      upfront_amount_min: 10000000,
      upfront_amount_max: 30000000,
      total_potential_amount_min: 100000000,
      total_potential_amount_max: 500000000,
      sort: ["upfront_amount:asc"],
      sort_by: "upfront_amount",
      sort_direction: "asc",
      display_mode: "landscape",
      analysis_dimension: "party_country",
      analysis_view: "table",
      analysis_limit: 20,
    },
    visibility: "private",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
    name: "Outbound licenses",
    saved_search_id: "saved-deal",
  });
});

it("saves and subscribes the complete typed regulatory query", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ id: "saved-regulatory" }))
    .mockResolvedValueOnce(json({ id: "topic-regulatory" }));

  await saveRegulatorySearch({
    name: " FDA pulmonary signals ",
    filters: {
      ...emptyRegulatorySearchFilters,
      query: "VX-101",
      agency: "FDA",
      jurisdiction: "US",
      eventType: "safety_signal",
      status: "active",
      designationType: "breakthrough_therapy",
      labelChangeType: "safety_update",
      boxedWarning: "false",
      safetySignalType: "adverse_event",
      safetySeverity: "serious",
      safetyStatus: "confirmed",
      decisionFrom: "2026-02-01",
      decisionTo: "2026-02-28",
      sourceUpdatedFrom: "2026-02-01",
      sourceUpdatedTo: "2026-02-28",
      sortBy: "source_updated_at",
      sortDirection: "asc",
    },
    shared: true,
    monitor: true,
  });

  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    name: "FDA pulmonary signals",
    query_type: "regulatory_search",
    query: {
      q: "VX-101",
      agency: "FDA",
      jurisdiction: "US",
      event_type: "safety_signal",
      status: "active",
      designation_type: "breakthrough_therapy",
      label_change_type: "safety_update",
      has_boxed_warning: false,
      safety_signal_type: "adverse_event",
      safety_severity: "serious",
      safety_status: "confirmed",
      decision_from: "2026-02-01",
      decision_to: "2026-02-28",
      source_updated_from: "2026-02-01",
      source_updated_to: "2026-02-28",
      sort: ["source_updated_at:asc"],
      sort_by: "source_updated_at",
      sort_direction: "asc",
      display_mode: "list",
      analysis_view: "chart",
    },
    visibility: "tenant",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
    name: "FDA pulmonary signals",
    saved_search_id: "saved-regulatory",
  });
});

it("saves and subscribes complete epidemiology and research-news queries", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ id: "saved-epidemiology" }))
    .mockResolvedValueOnce(json({ id: "topic-epidemiology" }))
    .mockResolvedValueOnce(json({ id: "saved-news" }))
    .mockResolvedValueOnce(json({ id: "topic-news" }));

  await saveEpidemiologySearch({
    name: " China NSCLC burden ",
    filters: {
      query: "registry",
      displayMode: "list" as const,
      analysisView: "chart" as const,
      diseaseEntityId: "550e8400-e29b-41d4-a716-446655440001",
      measure: "prevalence",
      geography: "China",
      unit: "patients",
      patientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
      populationScope: "adults",
      ageGroup: "18+",
      sex: "all",
      periodStartFrom: "2025-01-01",
      periodEndTo: "2025-12-31",
      sortBy: "value",
      sortDirection: "asc",
    },
    shared: false,
    monitor: true,
  });
  await saveNewsSearch({
    name: "ASCO research watch",
    filters: {
      query: "VX-101",
      analysisView: "chart" as const,
      entityId: "",
      eventType: "poster",
      publisher: "ASCO",
      language: "en",
      venue: "ASCO 2026",
      publishedFrom: "2026-01-01",
      publishedTo: "2026-12-31",
      contentScope: "research",
      displayMode: "timeline",
      sortBy: "venue",
      sortDirection: "asc",
    },
    shared: true,
    monitor: true,
  });

  expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
    name: "China NSCLC burden",
    query_type: "epidemiology_search",
    query: {
      q: "registry",
      disease_entity_id: "550e8400-e29b-41d4-a716-446655440001",
      measure: "prevalence",
      geography: "China",
      unit: "patients",
      patient_population_id: "550e8400-e29b-41d4-a716-446655440003",
      population_scope: "adults",
      age_group: "18+",
      sex: "all",
      period_start_from: "2025-01-01",
      period_end_to: "2025-12-31",
      sort: ["value:asc"],
      sort_by: "value",
      sort_direction: "asc",
      display_mode: "list",
      analysis_view: "chart",
    },
    visibility: "private",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
    name: "China NSCLC burden",
    saved_search_id: "saved-epidemiology",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toEqual({
    name: "ASCO research watch",
    query_type: "news_search",
    query: {
      q: "VX-101",
      event_type: "poster",
      publisher: "ASCO",
      language: "en",
      venue: "ASCO 2026",
      published_from: "2026-01-01",
      published_to: "2026-12-31",
      content_scope: "research",
      display_mode: "timeline",
      sort: ["venue:asc"],
      sort_by: "venue",
      sort_direction: "asc",
      analysis_view: "chart",
    },
    visibility: "tenant",
  });
  expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({
    name: "ASCO research watch",
    saved_search_id: "saved-news",
  });
});

it("maps regulatory and epidemiology full-result sorting to generated clients", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      query_schema_version: "test",
      applied_filters: [],
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
      sort_by: "title",
      sort_direction: "asc",
      facets: {},
      patient_populations: [],
      as_of: "2026-07-24T00:00:00Z",
      warnings: [],
    }),
  );

  await searchRegulatoryEvents(
    { ...emptyRegulatorySearchFilters, query: "VX-101", sortBy: "subject", sortDirection: "asc" },
    100,
  );
  let requestUrl = new URL(String(fetchMock.mock.calls.at(-1)?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/regulatory-event-timeline");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["subject:asc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();

  await searchEpidemiology(
    {
      displayMode: "list" as const,
      analysisView: "chart" as const,
      query: "NSCLC",
      diseaseEntityId: "11111111-1111-4111-8111-111111111111",
      measure: "",
      geography: "",
      unit: "",
      patientPopulationId: "",
      populationScope: "",
      ageGroup: "",
      sex: "",
      periodStartFrom: "",
      periodEndTo: "",
      sortBy: "value",
      sortDirection: "desc",
    },
    200,
  );
  requestUrl = new URL(String(fetchMock.mock.calls.at(-1)?.[0]), window.location.origin);
  expect(requestUrl.pathname).toBe("/api/v1/epidemiology-observations");
  expect(requestUrl.searchParams.get("disease_entity_id")).toBe("11111111-1111-4111-8111-111111111111");
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["value:desc"]);
  expect(requestUrl.searchParams.get("sort_by")).toBeNull();
});

it("does not treat empty multi-select collections as active pipeline filters", () => {
  // An empty filter set must not enable save/subscribe: an unfiltered subscription is a
  // full-library watch and fails closed on the server.
  expect(hasPipelineSearchFilter(emptyPipelineSearchFilters())).toBe(false);
  expect(hasPipelineSearchFilter({ ...emptyPipelineSearchFilters(), modalities: ["antibody"] })).toBe(true);
  expect(hasPipelineSearchFilter({ ...emptyPipelineSearchFilters(), programTags: ["first_in_class"] })).toBe(true);
});
