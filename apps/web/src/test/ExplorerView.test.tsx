import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useLayoutEffect, useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { addComparisonSetMembers, getComparisonSet, loadCollectionCatalog } from "../lib/contracts/collections";
import { loadDealFacetCatalog } from "../lib/contracts/deals";
import { loadEpidemiologyFacetCatalog } from "../lib/contracts/epidemiology";
import {
  type EntitySearchResult,
  getEntity,
  lookupEntityTypes,
  saveEntitySearch,
  searchEntities,
  suggestEntities,
} from "../lib/contracts/intelligence";
import { loadNewsFacetCatalog } from "../lib/contracts/news";
import { loadPatentFacetCatalog } from "../lib/contracts/patents";
import { loadPipelineFacetCatalog } from "../lib/contracts/pipeline";
import { loadRegulatoryFacetCatalog } from "../lib/contracts/regulatory";
import { loadTargetProfile } from "../lib/contracts/target";
import { setLocale } from "../lib/i18n";
import { resolveProfessionalDatePreset } from "../lib/professionalSearch";
import type { Entity } from "../lib/types";
import { ExplorerView } from "../views/ExplorerView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/intelligence", () => ({
  intelligenceKeys: {
    search: (
      query: string,
      entityTypes: string[],
      reviewStatus: string,
      sortBy = "relevance",
      sortDirection = "desc",
      offset = 0,
    ) => ["intelligence", { query, entityTypes, reviewStatus, sortBy, sortDirection, offset }],
    suggestions: (query: string, entityTypes: string[]) => ["suggestions", { query, entityTypes }],
    lookup: (query: string, entityType: string) => ["lookup", { query, entityType }],
    lookupMany: (query: string, entityTypes: readonly string[]) => ["lookup-many", { query, entityTypes }],
    entity: (entityId: string) => ["entity", entityId],
  },
  searchEntities: vi.fn(),
  suggestEntities: vi.fn(),
  lookupEntities: vi.fn(),
  lookupEntityTypes: vi.fn(),
  getEntity: vi.fn(),
  saveEntitySearch: vi.fn(),
}));
vi.mock("../lib/contracts/collections", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/collections")>();
  return { ...actual, loadCollectionCatalog: vi.fn(), getComparisonSet: vi.fn(), addComparisonSetMembers: vi.fn() };
});
vi.mock("../lib/contracts/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/deals")>();
  return { ...actual, loadDealFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/epidemiology", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/epidemiology")>();
  return { ...actual, loadEpidemiologyFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/news", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/news")>();
  return { ...actual, loadNewsFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/pipeline", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/pipeline")>();
  return { ...actual, loadPipelineFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/patents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/patents")>();
  return { ...actual, loadPatentFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/regulatory", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/regulatory")>();
  return { ...actual, loadRegulatoryFacetCatalog: vi.fn() };
});
vi.mock("../lib/contracts/target", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/target")>();
  return { ...actual, loadTargetProfile: vi.fn() };
});

const target = {
  id: "entity-1",
  canonical_entity_id: "entity-1",
  entity_type: "target" as const,
  name: "EGFR",
  description: "Epidermal growth factor receptor",
  external_ids: { HGNC: "3236" },
  attributes: {},
  review_status: "verified" as const,
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T11:00:00Z",
  match: {
    match_type: "alias" as const,
    match_relation: "exact" as const,
    matched_value: "ERBB1",
    namespace: null,
  },
};

const newsLinkedTarget = {
  ...target,
  id: "550e8400-e29b-41d4-a716-446655440002",
  canonical_entity_id: "550e8400-e29b-41d4-a716-446655440002",
};

const comparisonSet = {
  id: "22222222-2222-4222-8222-222222222222",
  owner_user_id: "user-1",
  name: "EGFR landscape",
  description: "",
  visibility: "private" as const,
  version: 1,
  member_count: 0,
  editable: true,
  created_at: "2026-07-18T10:00:00Z",
  updated_at: "2026-07-18T10:00:00Z",
};

function openAdvancedQuery(): void {
  fireEvent.click(screen.getByText(/^高级条件查询/, { selector: "summary" }));
}

it("changes memoized search headers and labels without repeating the query or clearing the draft", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.change(screen.getByRole("combobox", { name: "情报检索词" }), {
    target: { value: "未提交的中文名称 EGFR" },
  });
  const requests = vi.mocked(searchEntities).mock.calls.length;
  act(() => setLocale("en"));
  expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Entity search results" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Intelligence query" })).toHaveValue("未提交的中文名称 EGFR");
  expect(screen.getByRole("button", { name: "EGFR" })).toBeInTheDocument();
  expect(vi.mocked(searchEntities).mock.calls.length).toBe(requests);
  expect(onSearchChange).not.toHaveBeenCalled();
});

it("keeps a preview opener's DOM identity when route callbacks change and uses the latest handler", async () => {
  const first = vi.fn();
  const latest = vi.fn();
  function RouteOwner() {
    const [updated, setUpdated] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setUpdated(true)}>
          Commit new route callbacks
        </button>
        <ExplorerView
          initialQuery="EGFR"
          initialEntityType="target"
          initialReviewStatus="verified"
          onSearchChange={vi.fn()}
          onOpenEntity={vi.fn()}
          onSelectedEntityChange={(entity) => (updated ? latest : first)(entity)}
          onOpenSpecializedSearch={vi.fn()}
        />
      </>
    );
  }
  renderWithQueryClient(<RouteOwner />);
  const opener = await screen.findByRole("button", { name: "查看 EGFR 实体详情" });
  fireEvent.click(screen.getByRole("button", { name: "Commit new route callbacks" }));
  expect(screen.getByRole("button", { name: "查看 EGFR 实体详情" })).toBe(opener);
  fireEvent.click(opener);
  expect(latest).toHaveBeenCalledWith(target);
  expect(first).not.toHaveBeenCalled();
});

beforeEach(() => {
  vi.clearAllMocks();
  // Mirrors what the server echoes for the standard render props used across this file
  // (q=EGFR, entity_types=[target], review_status=verified).
  vi.mocked(searchEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [
      { field: "q", operator: "contains", value: "EGFR" },
      { field: "entity_types", operator: "in", value: ["target"] },
      { field: "review_status", operator: "eq", value: "verified" },
    ],
    items: [target],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: ["EGFR"],
    engine: "opensearch",
    took_ms: 12,
  });
  vi.mocked(suggestEntities).mockResolvedValue(["EGFR", "EGFR family"]);
  vi.mocked(lookupEntityTypes).mockResolvedValue([newsLinkedTarget]);
  vi.mocked(getEntity).mockResolvedValue(newsLinkedTarget);
  vi.mocked(loadTargetProfile).mockResolvedValue({
    entity: target,
    gene_symbol: "EGFR",
    uniprot_accession: "P00533",
    organism: "Homo sapiens",
    target_class: "SINGLE PROTEIN",
    activity_count: 0,
    program_count: 80,
    target_evidence_count: 0,
    as_of: "2026-08-12T00:00:00Z",
  });
  vi.mocked(saveEntitySearch).mockResolvedValue({ message: "已保存并启用监控" });
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [comparisonSet],
    total: [comparisonSet].length,
    limit: 25,
    offset: 0,
  });
  const comparisonDetail = {
    ...comparisonSet,
    members: [],
  };
  vi.mocked(getComparisonSet).mockResolvedValue(comparisonDetail);
  vi.mocked(addComparisonSetMembers).mockResolvedValue({
    ...comparisonDetail,
    version: 2,
    member_count: 1,
    members: [
      { id: "member-1", position: 0, added_by_user_id: "user-1", created_at: "2026-07-18T10:00:00Z", entity: target },
    ],
  });
  vi.mocked(loadPipelineFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      modality: { antibody: 8, "small molecule": 5 },
      innovation_type: { "First-in-class": 6, Biosimilar: 2 },
      therapeutic_area: { Oncology: 10, Immunology: 4 },
      drug_category: { "Small molecule": 7, Biologic: 5 },
      program_status: { active: 9, inactive: 2 },
      organization_role: { originator: 8, collaborator: 4 },
      organization_type: { biopharma: 7, biotech: 5 },
      organization_country_region: { CN: 8, US: 6 },
      has_clinical_results: { true: 7, false: 3 },
      clinical_result_evaluation: { positive: 5, superior: 2 },
      has_deal: { true: 6, false: 4 },
      deal_currency: { USD: 5, CNY: 2 },
      geography: { US: 9, China: 4 },
      development_rights_region: { Global: 8, China: 3 },
      commercialization_rights_region: { "Greater China": 6, Global: 5 },
      program_tag: { first_in_class: 7, best_in_class: 4 },
      milestone_type: { first_patient_in: 5, approval: 2 },
    },
    warnings: [],
  });
  vi.mocked(loadPatentFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      legal_status: { ACTIVE: 8, GRANTED: 5, EXPIRED: 2 },
      applicant: { "Victor Therapeutics": 4 },
    },
    warnings: [],
  });
  vi.mocked(loadDealFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      deal_type: { license: 8 },
      status: { active: 7 },
      direction: { outbound: 6 },
      territory: { Global: 5 },
      asset_modality: { antibody: 4 },
      asset_program_tag: { first_in_class: 3 },
      party_role: { licensor: 6 },
      party_country_region: { US: 5 },
      party_organization_type: { biopharma: 4 },
      development_phase_at_transaction: { phase_2: 5 },
      current_development_phase: { phase_3: 4 },
      right_type: { commercialization: 5 },
      rights_territory: { "Greater China": 4 },
      currency: { USD: 6 },
    },
    warnings: [],
  });
  vi.mocked(loadRegulatoryFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      agency: { FDA: 8 },
      jurisdiction: { US: 8 },
      event_type: { approval: 8 },
      status: { approved: 8 },
      designation_type: { breakthrough_therapy: 4 },
      label_change_type: { initial_label: 4 },
      has_boxed_warning: { true: 3, false: 5 },
      safety_signal_type: { adverse_event: 4 },
      safety_severity: { serious: 4 },
      safety_status: { confirmed: 4 },
    },
    warnings: [],
  });
  vi.mocked(loadEpidemiologyFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      measure: { prevalence: 8 },
      geography: { China: 8 },
      unit: { patients: 8 },
      population_scope: { adults: 8 },
      age_group: { "18+": 8 },
      sex: { all: 8 },
    },
    patient_populations: [
      {
        id: "550e8400-e29b-41d4-a716-446655440003",
        name: "EGFR positive adults",
        count: 8,
      },
    ],
    warnings: [],
  });
  vi.mocked(loadNewsFacetCatalog).mockResolvedValue({
    as_of: "2026-07-30T00:00:00Z",
    facets: {
      event_type: { conference_abstract: 8 },
      publisher: { ASCO: 8 },
      language: { en: 8 },
      venue: { "ASCO 2026": 8 },
    },
    warnings: [],
  });
});

it("searches through the typed contract and opens a governed target result", async () => {
  const openEntity = vi.fn();
  const openTargetPipeline = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={openEntity}
      onOpenTargetPipeline={openTargetPipeline}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  expect(await screen.findByRole("table", { name: "实体检索结果" })).toBeInTheDocument();
  expect(searchEntities).toHaveBeenCalledWith("EGFR", ["target"], "verified", expect.any(AbortSignal), {
    includeRelated: true,
    sortBy: "relevance",
    sortDirection: "desc",
    offset: 0,
  });
  expect(screen.getByRole("table", { name: "实体检索结果" })).not.toHaveTextContent("已核验");
  expect(screen.queryByText("opensearch")).not.toBeInTheDocument();
  expect(screen.queryByText("12 ms")).not.toBeInTheDocument();
  const matchContext = screen.getByText("别名精确匹配：ERBB1");
  expect(matchContext.closest("small")).toHaveAttribute(
    "title",
    "别名精确匹配：ERBB1 · Epidermal growth factor receptor",
  );
  expect(matchContext).not.toHaveTextContent("Epidermal growth factor receptor");
  expect(screen.getByText("Epidermal growth factor receptor")).toHaveClass("cell-subtitle");
  expect(screen.getByRole("button", { name: "EGFR" })).toHaveAttribute(
    "aria-description",
    "别名精确匹配：ERBB1 · Epidermal growth factor receptor",
  );
  const directTarget = screen.getByRole("region", { name: "EGFR 靶点直达" });
  expect(within(directTarget).getByText("靶点精确命中")).toBeInTheDocument();
  expect(await within(directTarget).findByText(/已关联 80 个研发项目/)).toBeVisible();
  expect(within(directTarget).getByRole("button", { name: "查看 80 个研发项目" })).toBeVisible();
  expect(loadTargetProfile).toHaveBeenCalledWith(target.id, expect.any(AbortSignal));
  const advancedQuery = screen.getByText(/^高级条件查询/, { selector: "summary" }).closest("details");
  expect(advancedQuery).not.toHaveAttribute("open");
  expect(screen.getByRole("button", { name: "查看 EGFR 研发项目" })).toBeVisible();
  openAdvancedQuery();
  expect(advancedQuery).toHaveAttribute("open");
  fireEvent.click(screen.getByRole("button", { name: "查看 EGFR 研发项目" }));
  expect(openTargetPipeline).toHaveBeenCalledWith(target.id);
  fireEvent.click(screen.getByRole("button", { name: "查看 EGFR 实体详情" }));
  fireEvent.click(screen.getByRole("button", { name: "查看研发项目" }));
  expect(openTargetPipeline).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole("button", { name: "打开靶点全景" }));
  expect(openEntity).toHaveBeenCalledWith(target);
});

it("does not show target direct access for a partial target match", async () => {
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [{ field: "q", operator: "contains", value: "EGFR" }],
    items: [{ ...target, match: { ...target.match, match_relation: "partial" } }],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: [],
    engine: "opensearch",
    took_ms: null,
  });

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenTargetPipeline={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "实体检索结果" });
  expect(screen.queryByRole("region", { name: "EGFR 靶点直达" })).not.toBeInTheDocument();
});

it("renders facet counts returned by the search contract without inventing totals", async () => {
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [{ field: "q", operator: "contains", value: "EGFR" }],
    items: [target],
    total: 1234,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: {
      entity_type: { drug: 987, target: 123, organization: 45 },
      review_status: { verified: 1111, draft: 123 },
    },
    suggestions: [],
    engine: "opensearch",
    took_ms: 12,
  });

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType=""
      initialReviewStatus=""
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const facetStripCount = (await screen.findAllByText("1234", { exact: true })).find((element) =>
    element.closest("fieldset.inline-filter-options"),
  );
  expect(facetStripCount).toBeDefined();
  expect(facetStripCount?.closest("fieldset")?.textContent).toContain("987");
  expect(facetStripCount?.closest("fieldset")?.textContent).toContain("123");
  expect(facetStripCount?.closest("fieldset")?.textContent).toContain("45");
  expect(screen.queryByText("1111", { exact: true })).not.toBeInTheDocument();
  expect(screen.getAllByText("123", { exact: true })).not.toHaveLength(0);
});

it("uses the current result total for the selected entity type instead of a broader facet count", async () => {
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [
      { field: "q", operator: "contains", value: "EGFR" },
      { field: "entity_types", operator: "in", value: ["target"] },
    ],
    items: [target],
    total: 8,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: {
      entity_type: { drug: 9, target: 22 },
      review_status: { verified: 31 },
    },
    suggestions: [],
    engine: "opensearch-hybrid",
    took_ms: 12,
  });

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  expect(await screen.findByRole("button", { name: "对象类型：靶点，8 条" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "对象类型：全部情报" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "对象类型：全部情报，8 条" })).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "实体类型筛选" })).not.toBeInTheDocument();
});

it("shows public database identifiers without governance terminology", async () => {
  const entityWithIdentity = {
    ...target,
    external_ids: {
      pharmcube_target: "internal-target-hash",
    },
    identity_identifiers: [
      {
        namespace: "HGNC",
        value: "3236",
        normalized_value: "3236",
        trusted_namespace: true,
        review_status: "verified" as const,
        source_document_id: "source-document-1",
      },
      {
        namespace: "pharmcube_target",
        value: "internal-target-hash",
        normalized_value: "internal-target-hash",
        trusted_namespace: false,
        review_status: "verified" as const,
        source_document_id: "source-document-2",
      },
    ],
  };
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [],
    items: [entityWithIdentity],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: [],
    engine: "opensearch",
    took_ms: 12,
  });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const table = await screen.findByRole("table", { name: "实体检索结果" });
  expect(within(table).getByText("HGNC: 3236")).toBeInTheDocument();
  fireEvent.click(within(table).getByRole("button", { name: "EGFR" }));
  const detail = await screen.findByRole("dialog", { name: "EGFR" });
  expect(within(detail).getByRole("heading", { name: "外部数据库标识" })).toBeInTheDocument();
  expect(within(detail).getByText("HGNC")).toBeInTheDocument();
  expect(within(detail).getByText("3236")).toBeInTheDocument();
  expect(table).not.toHaveTextContent("pharmcube_target");
  expect(table).not.toHaveTextContent("internal-target-hash");
  expect(detail).not.toHaveTextContent("pharmcube_target");
  expect(detail).not.toHaveTextContent("internal-target-hash");
  expect(detail).not.toHaveTextContent("规范");
  expect(detail).not.toHaveTextContent("可信命名空间");
  expect(detail).not.toHaveTextContent("已核验标识");
});

it("ignores governance review parameters in the external workspace", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="draft"
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "实体检索结果" });
  expect(searchEntities).toHaveBeenCalledWith("EGFR", ["target"], "verified", expect.any(AbortSignal), {
    includeRelated: true,
    sortBy: "relevance",
    sortDirection: "desc",
    offset: 0,
  });
  expect(screen.queryByRole("button", { name: /待核验/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /不纳入结果/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /历史版本/ })).not.toBeInTheDocument();
  await waitFor(() =>
    expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "relevance", "desc", 0, undefined),
  );
});

it("keeps internal provenance attributes out of the external entity detail", async () => {
  const entity = {
    ...target,
    attributes: {
      modality: "small molecule",
      origin: "governed_ai_extraction",
      source_document_ids: ["source-document-1"],
      internal_review_trace: { case_id: "case-1" },
    },
  };
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [],
    items: [entity],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: [],
    engine: "database",
    took_ms: null,
  });

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const table = await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.click(within(table).getByRole("button", { name: "EGFR" }));
  const detail = await screen.findByRole("dialog", { name: "EGFR" });
  expect(within(detail).getByText("补充信息")).toBeInTheDocument();
  expect(within(detail).getByText("药物模态")).toBeInTheDocument();
  expect(within(detail).getByText("small molecule")).toBeInTheDocument();
  expect(screen.queryByText("governed_ai_extraction")).not.toBeInTheDocument();
  expect(screen.queryByText("source_document_ids")).not.toBeInTheDocument();
  expect(screen.queryByText("source-document-1")).not.toBeInTheDocument();
  expect(screen.queryByText("internal_review_trace")).not.toBeInTheDocument();
});

it("renders full-result entity statistics and drills a governed bucket back into the query", async () => {
  const onSearchChange = vi.fn();
  const onAnalysisViewChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialDisplayMode="landscape"
      initialAnalysisView="table"
      onSearchChange={onSearchChange}
      onAnalysisViewChange={onAnalysisViewChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const landscape = await screen.findByRole("region", { name: "实体检索统计分析" });
  expect(within(landscape).getByRole("table", { name: "实体类型统计表" })).toBeInTheDocument();
  expect(within(landscape).getByText("靶点")).toBeInTheDocument();
  fireEvent.click(within(landscape).getAllByRole("button", { name: "筛选" })[0]);
  expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "relevance", "desc", 0, undefined);

  fireEvent.click(within(landscape).getByRole("button", { name: "图示" }));
  expect(onAnalysisViewChange).toHaveBeenCalledWith("chart");
});

it("keeps an explicit empty state when the statistics URL has no matches", async () => {
  vi.mocked(searchEntities).mockResolvedValueOnce({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [{ field: "q", operator: "contains", value: "unknown" }],
    items: [],
    total: 0,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: {}, review_status: {} },
    suggestions: [],
    engine: "opensearch",
    took_ms: 10,
  });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="unknown"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialDisplayMode="landscape"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  expect(await screen.findByText("未找到匹配实体")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "实体检索统计分析" })).not.toBeInTheDocument();
});

it("cancels an in-flight governed search and retries with the retained filters", async () => {
  const successfulResult: EntitySearchResult = {
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [
      { field: "q", operator: "contains", value: "EGFR" },
      { field: "entity_types", operator: "in", value: ["target"] },
      { field: "review_status", operator: "eq", value: "verified" },
    ],
    items: [target],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc" as const,
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: ["EGFR"],
    engine: "opensearch",
    took_ms: 12,
  };
  vi.mocked(searchEntities)
    .mockImplementationOnce(
      (_query, _types, _review, signal) =>
        new Promise((_, reject) => {
          signal?.addEventListener("abort", () => reject(new Error("request aborted")), { once: true });
        }),
    )
    .mockResolvedValueOnce(successfulResult);

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  fireEvent.click(await screen.findByRole("button", { name: "取消查询" }));
  expect(await screen.findByText("查询已取消", { exact: true })).toBeVisible();
  expect(screen.getByLabelText("情报检索词")).toHaveValue("EGFR");
  fireEvent.click(screen.getByRole("button", { name: "重新查询" }));
  expect(await screen.findByRole("table", { name: "实体检索结果" })).toBeVisible();
  expect(searchEntities).toHaveBeenCalledTimes(2);
});

it("replaces a lightweight row snapshot with the authoritative full preview without losing match context", async () => {
  const onSelectedEntityChange = vi.fn();
  const renderPreview = (selectedEntity: Entity | null, initialSelectedEntityId: string | null) => (
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
      initialSelectedEntityId={initialSelectedEntityId}
      selectedEntity={selectedEntity}
      onSelectedEntityChange={onSelectedEntityChange}
    />
  );
  const rendered = renderWithQueryClient(renderPreview(null, null));
  await screen.findByRole("button", { name: "EGFR" });
  fireEvent.click(screen.getByRole("button", { name: "查看 EGFR 实体详情" }));
  const complete = {
    ...target,
    match: undefined,
    description: "Full authoritative description",
    aliases: Array.from({ length: 30 }, (_, index) => `CODE-${index}`),
  };
  rendered.rerender(renderPreview(complete, target.id));
  const drawer = screen.getByRole("dialog", { name: "EGFR" });
  expect(within(drawer).getByText("Full authoritative description")).toBeVisible();
  fireEvent.click(within(drawer).getByText("更多别名（24）"));
  expect(within(drawer).getByText("CODE-29")).toBeVisible();
  expect(within(drawer).getByText("别名精确匹配：ERBB1")).toBeVisible();
});

it("restores, closes and reports states for a URL-controlled quick detail", async () => {
  const onSelectedEntityChange = vi.fn();
  const { rerender } = renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialSelectedEntityId={target.id}
      selectedEntity={target}
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onSelectedEntityChange={onSelectedEntityChange}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const controlledDrawer = await screen.findByRole("dialog", { name: "EGFR" });
  expect(controlledDrawer).toBeVisible();
  expect(controlledDrawer.parentElement?.parentElement).toBe(document.body);
  fireEvent.click(screen.getByRole("button", { name: "关闭实体详情" }));
  expect(onSelectedEntityChange).toHaveBeenCalledWith(null);

  rerender(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialSelectedEntityId={target.id}
      selectedEntity={null}
      selectedEntityLoading
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onSelectedEntityChange={onSelectedEntityChange}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  expect(screen.getByText("正在加载实体详情")).toBeVisible();

  rerender(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialSelectedEntityId={target.id}
      selectedEntity={null}
      selectedEntityError="实体读取失败"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onSelectedEntityChange={onSelectedEntityChange}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  expect(screen.getByText("实体读取失败")).toBeVisible();
});

it("renders the applied-condition bar from the server contract, not from unsubmitted input", async () => {
  vi.mocked(searchEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [
      { field: "q", operator: "contains", value: "EGFR" },
      { field: "entity_types", operator: "in", value: ["target"] },
      { field: "review_status", operator: "eq", value: "verified" },
    ],
    items: [target],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: [],
    engine: "opensearch",
    took_ms: 9,
  });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  const bar = await screen.findByRole("region", { name: "已应用查询条件" });
  expect(within(bar).getByText("关键词")).toBeInTheDocument();
  expect(within(bar).getByText("EGFR")).toBeInTheDocument();
  expect(within(bar).getByText("靶点")).toBeInTheDocument();
  expect(within(bar).queryByText("已核验")).not.toBeInTheDocument();

  // Typing without submitting must not change the applied-condition bar: it reflects the
  // query the server actually executed, not the draft in the input.
  fireEvent.change(screen.getByLabelText("情报检索词"), { target: { value: "BRAF not submitted" } });
  expect(within(bar).getByText("EGFR")).toBeInTheDocument();
  expect(within(bar).queryByText("BRAF not submitted")).not.toBeInTheDocument();
});

it("adds selected result entities to one versioned comparison set without repeating the search", async () => {
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.click(screen.getByRole("checkbox", { name: "选择对比 EGFR" }));
  expect(screen.getByText("已选 1/20 项")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "加入列表（1）" }));

  const dialog = await screen.findByRole("dialog", { name: "加入对比列表" });
  expect(await within(dialog).findByLabelText("目标列表")).toHaveValue(comparisonSet.id);
  expect(within(dialog).getByText("完成后共 1/20 个实体")).toBeVisible();
  fireEvent.click(within(dialog).getByRole("button", { name: "确认加入" }));

  await waitFor(() =>
    expect(addComparisonSetMembers).toHaveBeenCalledWith(comparisonSet.id, {
      entity_ids: [target.id],
      expected_version: 1,
    }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("1 个实体已加入 EGFR landscape");
  expect(screen.getByRole("checkbox", { name: "选择对比 EGFR" })).not.toBeChecked();
});

it("keeps the result selection recoverable when the comparison set changed concurrently", async () => {
  vi.mocked(addComparisonSetMembers).mockRejectedValueOnce(new Error("对比列表版本已变化"));
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.click(screen.getByRole("checkbox", { name: "选择对比 EGFR" }));
  fireEvent.click(screen.getByRole("button", { name: "加入列表（1）" }));
  const dialog = await screen.findByRole("dialog", { name: "加入对比列表" });
  await within(dialog).findByLabelText("目标列表");
  fireEvent.click(within(dialog).getByRole("button", { name: "确认加入" }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent("对比列表版本已变化");
  expect(screen.getByRole("checkbox", { name: "取消选择对比 EGFR" })).toBeChecked();
  expect(loadCollectionCatalog).toHaveBeenCalledTimes(2);
});

it("sorts the complete hit set and pages through URL-owned query state", async () => {
  vi.mocked(searchEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [{ field: "q", operator: "contains", value: "EGFR" }],
    items: [target],
    total: 201,
    limit: 100,
    offset: 100,
    sort_by: "relevance",
    sort_direction: "desc",
    facets: { entity_type: { target: 201 }, review_status: { verified: 201 } },
    suggestions: ["EGFR"],
    engine: "opensearch-hybrid",
    took_ms: 18,
  });
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialSortBy="relevance"
      initialSortDirection="desc"
      initialOffset={100}
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  expect(await screen.findByText("第 2 / 3 页")).toBeInTheDocument();
  expect(screen.getByText("共 201 条")).toBeInTheDocument();
  expect(screen.getByText(/全部结果按相关性降序/)).toBeInTheDocument();
  fireEvent.click(within(screen.getByRole("columnheader", { name: /名称/ })).getByRole("button"));
  expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "name", "asc", 0, [
    { field: "name", direction: "asc" },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "relevance", "desc", 200, undefined);
  fireEvent.click(screen.getByRole("button", { name: "上一页" }));
  expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "relevance", "desc", 0, undefined);
});

it("restores field sorting from canonical URL state into the accessible table header", async () => {
  vi.mocked(searchEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [{ field: "q", operator: "contains", value: "EGFR" }],
    items: [target],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "name",
    sort_direction: "asc",
    sort: [{ field: "name", direction: "asc" }],
    facets: { entity_type: { target: 1 }, review_status: { verified: 1 } },
    suggestions: ["EGFR"],
    engine: "opensearch",
    took_ms: 8,
  });

  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialSortBy="name"
      initialSortDirection="asc"
      initialSort={[{ field: "name", direction: "asc" }]}
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  expect(await screen.findByText(/全部结果按名称升序/)).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: /名称/ })).toHaveAttribute("aria-sort", "ascending");
});

it("saves the normalized query and reports a partial monitoring outcome without retrying the write", async () => {
  vi.mocked(saveEntitySearch).mockResolvedValue({ message: "检索已保存，但监控未启用：上游不可用" });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.click(screen.getByRole("button", { name: "保存检索" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "EGFR landscape" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() => expect(saveEntitySearch).toHaveBeenCalledOnce());
  expect(vi.mocked(saveEntitySearch).mock.calls[0]?.[0]).toEqual({
    includeRelated: true,
    name: "EGFR landscape",
    query: "EGFR",
    entityTypes: ["target"],
    reviewStatus: "verified",
    sortBy: "relevance",
    sortDirection: "desc",
    displayMode: "list",
    analysisView: "chart",
    shared: false,
    monitor: true,
  });
  expect(await screen.findByText("检索已保存，但监控未启用：上游不可用")).toBeInTheDocument();
  expect(saveEntitySearch).toHaveBeenCalledOnce();
});

it("saves the statistics presentation state with the entity query", async () => {
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      initialDisplayMode="landscape"
      initialAnalysisView="table"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("region", { name: "实体检索统计分析" });
  fireEvent.click(screen.getByRole("button", { name: "保存检索" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "EGFR statistics" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() => expect(saveEntitySearch).toHaveBeenCalledOnce());
  expect(vi.mocked(saveEntitySearch).mock.calls[0]?.[0]).toMatchObject({
    displayMode: "landscape",
    analysisView: "table",
  });
});

it("presents a rejected save in the active dialog and retains the same query for an explicit retry", async () => {
  vi.mocked(saveEntitySearch)
    .mockRejectedValueOnce(new Error("暂时无法保存，请重试"))
    .mockResolvedValueOnce({ message: "检索已保存" });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  const opener = screen.getByRole("button", { name: "保存检索" });
  fireEvent.click(opener);
  const dialog = screen.getByRole("dialog", { name: "保存当前检索" });
  fireEvent.change(within(dialog).getByLabelText("名称"), { target: { value: "Reviewed EGFR query" } });
  fireEvent.click(within(dialog).getByLabelText("企业内共享该检索"));
  fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent("暂时无法保存，请重试");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(within(dialog).getByLabelText("名称")).toHaveValue("Reviewed EGFR query");
  expect(within(dialog).getByLabelText("企业内共享该检索")).toBeChecked();
  expect(saveEntitySearch).toHaveBeenCalledOnce();
  const submitted = vi.mocked(saveEntitySearch).mock.calls[0];
  fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));
  expect(await screen.findByText("检索已保存")).toBeVisible();
  expect(saveEntitySearch).toHaveBeenCalledTimes(2);
  expect(vi.mocked(saveEntitySearch).mock.calls[1]).toEqual(submitted);
  fireEvent.click(opener);
  expect(within(screen.getByRole("dialog", { name: "保存当前检索" })).queryByRole("alert")).not.toBeInTheDocument();
});

it("never commits another query's rows while restoring applied conditions", async () => {
  const previousResult = await searchEntities("EGFR", ["target"], "verified");
  let releaseNext: ((value: EntitySearchResult) => void) | undefined;
  const nextResult = new Promise<EntitySearchResult>((resolve) => {
    releaseNext = resolve;
  });
  vi.mocked(searchEntities).mockImplementation((query) =>
    query === "ALK" ? nextResult : Promise.resolve(previousResult),
  );
  const restoredSnapshots: string[] = [];
  function Harness() {
    const [applied, setApplied] = useState("EGFR");
    useLayoutEffect(() => {
      if (applied === "ALK")
        restoredSnapshots.push(screen.queryByRole("table", { name: "实体检索结果" })?.textContent ?? "");
    }, [applied]);
    return (
      <>
        <button type="button" onClick={() => setApplied("ALK")}>
          恢复其他检索
        </button>
        <ExplorerView
          initialQuery={applied}
          initialEntityType="target"
          initialReviewStatus="verified"
          onSearchChange={vi.fn()}
          onOpenEntity={vi.fn()}
          onOpenSpecializedSearch={vi.fn()}
        />
      </>
    );
  }
  renderWithQueryClient(<Harness />);
  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.click(screen.getByRole("button", { name: "恢复其他检索" }));
  releaseNext?.({ ...previousResult, items: [], total: 0, applied_filters: [] });
  expect(restoredSnapshots).toEqual([""]);
  await screen.findByText("未找到匹配实体");
});

it("saves the displayed applied query instead of an unsubmitted edit", async () => {
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  fireEvent.change(screen.getByLabelText("情报检索词"), { target: { value: "ALK" } });
  fireEvent.click(screen.getByRole("button", { name: "保存检索" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "Displayed result" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));
  await waitFor(() => expect(saveEntitySearch).toHaveBeenCalledOnce());
  expect(vi.mocked(saveEntitySearch).mock.calls[0]?.[0]).toMatchObject({ query: "EGFR", entityTypes: ["target"] });
});

it("loads bounded entity suggestions and submits only published data", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery=""
      initialEntityType="target"
      initialReviewStatus=""
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  const input = screen.getByLabelText("情报检索词");
  fireEvent.change(input, { target: { value: "PD-1" } });
  expect(await screen.findByRole("option", { name: /EGFR family/ }, { timeout: 5_000 })).toBeInTheDocument();
  expect(suggestEntities).toHaveBeenCalledWith("PD-1", ["target"], expect.any(AbortSignal));
  fireEvent.click(screen.getByRole("button", { name: "检索" }));
  expect(onSearchChange).toHaveBeenCalledWith("PD-1", ["target"], "verified", "relevance", "desc", 0, undefined);
});

it("keeps the suggestion surface stable while focus moves to the submit button", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery=""
      initialEntityType="target"
      initialReviewStatus=""
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  const input = screen.getByLabelText("情报检索词");
  const submit = screen.getByRole("button", { name: "检索" });
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: "PD-1" } });
  expect(await screen.findByRole("option", { name: /EGFR family/ }, { timeout: 5_000 })).toBeInTheDocument();

  fireEvent.blur(input, { relatedTarget: submit });
  expect(screen.getByRole("option", { name: /EGFR family/ })).toBeInTheDocument();
  fireEvent.click(submit);

  expect(onSearchChange).toHaveBeenCalledWith("PD-1", ["target"], "verified", "relevance", "desc", 0, undefined);
});

it("submits the typed query when Enter is pressed while suggestions are open", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery=""
      initialEntityType="target"
      initialReviewStatus=""
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  const input = screen.getByLabelText("情报检索词");
  fireEvent.change(input, { target: { value: "EGFR" } });
  expect(await screen.findByRole("option", { name: /EGFR family/ }, { timeout: 5_000 })).toBeInTheDocument();

  fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

  expect(onSearchChange).toHaveBeenCalledWith("EGFR", ["target"], "verified", "relevance", "desc", 0, undefined);
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("combines entity types with same-dimension OR semantics", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus=""
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });

  fireEvent.click(screen.getByRole("button", { name: /对象类型：药物/ }));

  expect(onSearchChange).toHaveBeenCalledWith(
    "EGFR",
    ["drug", "target"],
    "verified",
    "relevance",
    "desc",
    0,
    undefined,
  );
  expect(screen.getByRole("button", { name: /对象类型：药物/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /对象类型：靶点/ })).toHaveAttribute("aria-pressed", "true");
});

it("builds a validated professional query and hands complete URL state to the authoritative domain view", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );

  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "临床试验" }));
  fireEvent.change(screen.getByLabelText("注册平台"), { target: { value: "ClinicalTrials.gov" } });
  fireEvent.change(screen.getByLabelText("招募状态"), { target: { value: "RECRUITING" } });
  fireEvent.change(screen.getByLabelText("临床分期"), { target: { value: "PHASE2" } });
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("结果发布日期时间范围"), { target: { value: "last_6_months" } });
  fireEvent.click(screen.getByText("试验属性与结果评价"));
  fireEvent.change(screen.getByLabelText("试验简称"), { target: { value: "BRIDGE-001" } });
  fireEvent.change(screen.getByLabelText("发起类型"), { target: { value: "ist" } });
  fireEvent.change(screen.getByLabelText("治疗线次"), { target: { value: "first_line" } });
  fireEvent.change(screen.getByLabelText("结果最优评价"), { target: { value: "positive" } });
  fireEvent.click(screen.getByText("关键结果与发表证据"));
  fireEvent.change(screen.getByLabelText("关键结果"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("发表编号"), { target: { value: "PMID:12345678" } });
  fireEvent.change(screen.getByLabelText("会议"), { target: { value: "ASCO 2026" } });
  fireEvent.change(screen.getByLabelText("结果披露日期时间范围"), { target: { value: "last_month" } });
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "false" } });
  expect(screen.getByLabelText("结果最优评价")).toBeDisabled();
  expect(screen.getByLabelText("结果最优评价")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("结果最优评价"), { target: { value: "positive" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 临床试验" }));
  const expectedRange = resolveProfessionalDatePreset("last_6_months");
  const expectedDisclosureRange = resolveProfessionalDatePreset("last_month");
  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      workbench: "research",
      view: "trials",
      query: "EGFR",
      registry: "ClinicalTrials.gov",
      trialStatus: "RECRUITING",
      trialPhase: "PHASE2",
      trialHasResults: "true",
      trialAcronym: "BRIDGE-001",
      trialInitiationType: "ist",
      trialTherapyLine: "first_line",
      trialResultEvaluation: "positive",
      trialHasKeyResult: "true",
      trialPublicationId: "PMID:12345678",
      trialConference: "ASCO 2026",
      trialDisclosedFrom: expectedDisclosureRange.from,
      trialDisclosedTo: expectedDisclosureRange.to,
      trialResultsPostedFrom: expectedRange.from,
      trialResultsPostedTo: expectedRange.to,
      offset: 0,
    }),
  );
  expect(screen.getByRole("region", { name: "已应用查询条件" })).toHaveTextContent("靶点");
  expect(screen.getByRole("region", { name: "已应用查询条件" })).not.toHaveTextContent("已核验");
});

it("hands the complete governed patent query to the authoritative patent view", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();

  fireEvent.click(screen.getByRole("button", { name: "专利情报" }));
  expect(await screen.findByRole("option", { name: "授权 (5)" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "关联实体筛选" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("关联实体类型"), { target: { value: "drug" } });
  fireEvent.change(screen.getByLabelText("申请人"), { target: { value: "Victor Therapeutics" } });
  fireEvent.change(screen.getByLabelText("法律状态"), { target: { value: "GRANTED" } });
  fireEvent.change(screen.getByLabelText("优先权日期时间范围"), { target: { value: "custom" } });
  const priorityRange = screen.getByRole("group", { name: "优先权日期" });
  fireEvent.change(within(priorityRange).getByLabelText("起"), { target: { value: "2020-01-01" } });
  fireEvent.change(within(priorityRange).getByLabelText("止"), { target: { value: "2022-12-31" } });
  fireEvent.change(screen.getByLabelText("到期日期时间范围"), { target: { value: "custom" } });
  const expirationRange = screen.getByRole("group", { name: "到期日期" });
  fireEvent.change(within(expirationRange).getByLabelText("起"), { target: { value: "2035-01-01" } });
  fireEvent.change(within(expirationRange).getByLabelText("止"), { target: { value: "2040-12-31" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 专利情报" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "patents",
      query: "EGFR",
      applicant: "Victor Therapeutics",
      legalStatus: "GRANTED",
      patentPriorityFrom: "2020-01-01",
      patentPriorityTo: "2022-12-31",
      patentExpirationFrom: "2035-01-01",
      patentExpirationTo: "2040-12-31",
    }),
  );
});

it("hands the complete governed deal query to the authoritative deal view", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "交易与公司" }));
  expect(await screen.findByRole("option", { name: "许可 (8)" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "交易药品筛选" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "关联靶点筛选" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "关联适应症筛选" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "参与机构筛选" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("交易类型"), { target: { value: "license" } });
  fireEvent.change(screen.getByLabelText("交易状态"), { target: { value: "active" } });
  fireEvent.change(screen.getByLabelText("交易方向"), { target: { value: "outbound" } });
  fireEvent.click(screen.getByText("更多交易条件"));
  fireEvent.change(screen.getByLabelText("方向参照地区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("交易地域"), { target: { value: "Global" } });
  fireEvent.change(screen.getByLabelText("参与角色"), { target: { value: "licensor" } });
  fireEvent.change(screen.getByLabelText("机构所在地区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("机构类型"), { target: { value: "biopharma" } });
  fireEvent.change(screen.getByLabelText("交易时阶段"), { target: { value: "phase_2" } });
  fireEvent.change(screen.getByLabelText("当前最高阶段"), { target: { value: "phase_3" } });
  fireEvent.change(screen.getByLabelText("权益类型"), { target: { value: "commercialization" } });
  fireEvent.change(screen.getByLabelText("权益地区"), { target: { value: "Greater China" } });
  fireEvent.change(screen.getByLabelText("币种"), { target: { value: "USD" } });
  const modalities = screen.getByRole("group", { name: "资产模态" });
  fireEvent.click(within(modalities).getByLabelText("资产模态：全部"));
  fireEvent.click(within(modalities).getByRole("checkbox", { name: /antibody/ }));
  const tags = screen.getByRole("group", { name: "资产项目标签" });
  fireEvent.click(within(tags).getByLabelText("资产项目标签：全部"));
  fireEvent.click(within(tags).getByRole("checkbox", { name: /first_in_class/ }));
  fireEvent.change(screen.getByLabelText("终止日期时间范围"), { target: { value: "custom" } });
  const terminatedRange = screen.getByRole("group", { name: "终止日期" });
  fireEvent.change(within(terminatedRange).getByLabelText("起"), { target: { value: "2026-02-01" } });
  fireEvent.change(within(terminatedRange).getByLabelText("止"), { target: { value: "2026-02-28" } });
  fireEvent.change(screen.getByLabelText("首付款下限"), { target: { value: "10000000" } });
  fireEvent.change(screen.getByLabelText("首付款上限"), { target: { value: "30000000" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 交易与公司" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "deals",
      dealType: "license",
      dealStatus: "active",
      dealDirection: "outbound",
      dealDirectionReferenceJurisdiction: "US",
      dealTerritory: "Global",
      dealAssetModalities: ["antibody"],
      dealAssetProgramTags: ["first_in_class"],
      dealPartyRole: "licensor",
      dealPartyCountryRegion: "US",
      dealPartyOrganizationType: "biopharma",
      dealDevelopmentPhaseAtTransaction: "phase_2",
      dealCurrentDevelopmentPhase: "phase_3",
      dealRightType: "commercialization",
      dealRightsTerritory: "Greater China",
      dealCurrency: "USD",
      dealTerminatedFrom: "2026-02-01",
      dealTerminatedTo: "2026-02-28",
      dealUpfrontAmountMin: "10000000",
      dealUpfrontAmountMax: "30000000",
    }),
  );
});

it("hands the complete governed regulatory query to the authoritative regulatory view", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "监管与安全" }));
  expect(await screen.findByRole("option", { name: "FDA (8)" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("监管机构"), { target: { value: "FDA" } });
  fireEvent.change(screen.getByLabelText("辖区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("事件类型"), { target: { value: "approval" } });
  fireEvent.change(screen.getByLabelText("事件状态"), { target: { value: "approved" } });
  fireEvent.change(screen.getByLabelText("监管决定日期时间范围"), { target: { value: "custom" } });
  const decisionRange = screen.getByRole("group", { name: "监管决定日期" });
  fireEvent.change(within(decisionRange).getByLabelText("起"), { target: { value: "2026-01-01" } });
  fireEvent.change(within(decisionRange).getByLabelText("止"), { target: { value: "2026-01-31" } });
  fireEvent.click(screen.getByText("更多监管与安全条件"));
  fireEvent.change(screen.getByLabelText("认定资格"), { target: { value: "breakthrough_therapy" } });
  fireEvent.change(screen.getByLabelText("标签变更"), { target: { value: "initial_label" } });
  fireEvent.change(screen.getByLabelText("黑框警告"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("安全信号"), { target: { value: "adverse_event" } });
  fireEvent.change(screen.getByLabelText("严重程度"), { target: { value: "serious" } });
  fireEvent.change(screen.getByLabelText("信号状态"), { target: { value: "confirmed" } });
  fireEvent.change(screen.getByLabelText("来源更新日期时间范围"), { target: { value: "custom" } });
  const sourceRange = screen.getByRole("group", { name: "来源更新日期" });
  fireEvent.change(within(sourceRange).getByLabelText("起"), { target: { value: "2026-02-01" } });
  fireEvent.change(within(sourceRange).getByLabelText("止"), { target: { value: "2026-02-28" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 监管与安全" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "regulatory",
      query: "EGFR",
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
      regulatoryDecisionTo: "2026-01-31",
      regulatorySourceUpdatedFrom: "2026-02-01",
      regulatorySourceUpdatedTo: "2026-02-28",
    }),
  );
});

it("expands advanced pipeline conditions and preserves their complete URL-owned query", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();

  const modality = await screen.findByRole("group", { name: "药物模态" });
  fireEvent.click(within(modality).getByLabelText("药物模态：全部"));
  fireEvent.click(within(modality).getByRole("checkbox", { name: /antibody/ }));
  fireEvent.click(within(modality).getByRole("checkbox", { name: /small molecule/ }));
  const innovationTypes = screen.getByRole("group", { name: "创新类型" });
  fireEvent.click(within(innovationTypes).getByLabelText("创新类型：全部"));
  fireEvent.click(within(innovationTypes).getByRole("checkbox", { name: /First-in-class/ }));
  fireEvent.click(within(innovationTypes).getByRole("checkbox", { name: /Biosimilar/ }));
  const therapeuticAreas = screen.getByRole("group", { name: "治疗领域" });
  fireEvent.click(within(therapeuticAreas).getByLabelText("治疗领域：全部"));
  fireEvent.click(within(therapeuticAreas).getByRole("checkbox", { name: /Oncology/ }));
  fireEvent.click(within(therapeuticAreas).getByRole("checkbox", { name: /Immunology/ }));
  const drugCategories = screen.getByRole("group", { name: "药品类别" });
  fireEvent.click(within(drugCategories).getByLabelText("药品类别：全部"));
  fireEvent.click(within(drugCategories).getByRole("checkbox", { name: /Small molecule/ }));
  fireEvent.click(within(drugCategories).getByRole("checkbox", { name: /Biologic/ }));
  fireEvent.change(screen.getByRole("combobox", { name: "项目状态" }), { target: { value: "active" } });
  fireEvent.change(screen.getByRole("combobox", { name: "记录地区" }), { target: { value: "US" } });
  fireEvent.click(screen.getByText("更多管线条件"));
  fireEvent.change(screen.getByLabelText("全球最高阶段"), { target: { value: "phase_2" } });
  fireEvent.change(screen.getByLabelText("中国最高阶段"), { target: { value: "phase_1" } });
  fireEvent.change(screen.getByRole("combobox", { name: "研发权益地区" }), { target: { value: "Global" } });
  fireEvent.change(screen.getByRole("combobox", { name: "商业化权益地区" }), {
    target: { value: "Greater China" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "机构角色" }), { target: { value: "originator" } });
  fireEvent.change(screen.getByRole("combobox", { name: "机构类型" }), { target: { value: "biopharma" } });
  fireEvent.change(screen.getByRole("combobox", { name: "机构所在地区" }), { target: { value: "CN" } });
  const programTags = screen.getByRole("group", { name: "项目标签" });
  fireEvent.click(within(programTags).getByLabelText("项目标签：全部"));
  fireEvent.click(within(programTags).getByRole("checkbox", { name: /first_in_class/ }));
  fireEvent.change(screen.getByRole("combobox", { name: "里程碑类型" }), {
    target: { value: "first_patient_in" },
  });
  fireEvent.change(screen.getByLabelText("里程碑日期时间范围"), { target: { value: "custom" } });
  const milestoneRange = screen.getByRole("group", { name: "里程碑日期" });
  fireEvent.change(within(milestoneRange).getByLabelText("起"), { target: { value: "2026-05-01" } });
  fireEvent.change(within(milestoneRange).getByLabelText("止"), { target: { value: "2026-06-30" } });
  fireEvent.click(screen.getByText("临床结果与交易信号"));
  fireEvent.change(screen.getByRole("combobox", { name: "是否已有临床结果" }), { target: { value: "true" } });
  fireEvent.change(screen.getByRole("combobox", { name: "临床结果评价" }), { target: { value: "positive" } });
  fireEvent.change(screen.getByRole("combobox", { name: "是否已有临床结果" }), { target: { value: "false" } });
  expect(screen.getByRole("combobox", { name: "临床结果评价" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "临床结果评价" })).toHaveValue("");
  fireEvent.change(screen.getByRole("combobox", { name: "是否已有临床结果" }), { target: { value: "true" } });
  fireEvent.change(screen.getByRole("combobox", { name: "临床结果评价" }), { target: { value: "positive" } });
  fireEvent.change(screen.getByRole("combobox", { name: "是否存在交易记录" }), { target: { value: "true" } });
  fireEvent.change(screen.getByRole("combobox", { name: "交易币种" }), { target: { value: "USD" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "潜在总额下限" }), {
    target: { value: "100000000" },
  });
  fireEvent.change(screen.getByRole("spinbutton", { name: "潜在总额上限" }), {
    target: { value: "500000000" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "是否存在交易记录" }), { target: { value: "false" } });
  expect(screen.getByRole("combobox", { name: "交易币种" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "交易币种" })).toHaveValue("");
  expect(screen.getByRole("spinbutton", { name: "潜在总额下限" })).toBeDisabled();
  expect(screen.getByRole("spinbutton", { name: "潜在总额下限" })).toHaveValue(null);
  expect(screen.getByRole("spinbutton", { name: "潜在总额上限" })).toHaveValue(null);
  fireEvent.change(screen.getByRole("combobox", { name: "是否存在交易记录" }), { target: { value: "true" } });
  fireEvent.change(screen.getByRole("combobox", { name: "交易币种" }), { target: { value: "USD" } });
  fireEvent.change(screen.getByRole("spinbutton", { name: "潜在总额下限" }), {
    target: { value: "100000000" },
  });
  fireEvent.change(screen.getByRole("spinbutton", { name: "潜在总额上限" }), {
    target: { value: "500000000" },
  });
  fireEvent.click(screen.getByRole("button", { name: "查询 药物与管线" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "pipeline",
      query: "EGFR",
      pipelineModalities: ["antibody", "small molecule"],
      pipelineInnovationTypes: ["First-in-class", "Biosimilar"],
      pipelineTherapeuticAreas: ["Oncology", "Immunology"],
      pipelineDrugCategories: ["Small molecule", "Biologic"],
      pipelineProgramStatus: "active",
      pipelineOrganizationRole: "originator",
      pipelineOrganizationType: "biopharma",
      pipelineOrganizationCountryRegion: "CN",
      geography: "US",
      pipelineGlobalPhase: "phase_2",
      pipelineChinaPhase: "phase_1",
      pipelineDevelopmentRightsRegion: "Global",
      pipelineCommercializationRightsRegion: "Greater China",
      pipelineProgramTags: ["first_in_class"],
      pipelineMilestoneType: "first_patient_in",
      pipelineMilestoneFrom: "2026-05-01",
      pipelineMilestoneTo: "2026-06-30",
      pipelineHasClinicalResults: "true",
      pipelineClinicalResultEvaluation: "positive",
      pipelineHasDeal: "true",
      pipelineDealCurrency: "USD",
      pipelineDealTotalPotentialAmountMin: "100000000",
      pipelineDealTotalPotentialAmountMax: "500000000",
    }),
  );
});

it("surfaces and recovers the authoritative professional facet catalog failure", async () => {
  vi.mocked(loadPipelineFacetCatalog)
    .mockRejectedValueOnce(new Error("Pipeline facet catalog unavailable"))
    .mockResolvedValueOnce({
      as_of: "2026-07-30T00:00:00Z",
      facets: {
        modality: { antibody: 8 },
        innovation_type: { "First-in-class": 6 },
        therapeutic_area: { Oncology: 10 },
        drug_category: { Biologic: 5 },
        program_status: { active: 9 },
        organization_role: { originator: 8 },
        organization_type: { biopharma: 7 },
        organization_country_region: { CN: 8 },
        has_clinical_results: { true: 7, false: 3 },
        clinical_result_evaluation: { positive: 5, superior: 2 },
        has_deal: { true: 6, false: 4 },
        deal_currency: { USD: 5, CNY: 2 },
        geography: { US: 9 },
        development_rights_region: { Global: 8 },
        commercialization_rights_region: { "Greater China": 6 },
        program_tag: { first_in_class: 7 },
        milestone_type: { first_patient_in: 5 },
      },
      warnings: [],
    });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );

  openAdvancedQuery();

  const alert = await screen.findByRole("alert");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(alert).toHaveTextContent("管线筛选选项暂不可用");
  fireEvent.click(within(alert).getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("group", { name: "药物模态" })).toBeInTheDocument();
  expect(await screen.findByRole("group", { name: "创新类型" })).toBeInTheDocument();
  expect(await screen.findByRole("group", { name: "治疗领域" })).toBeInTheDocument();
  expect(await screen.findByRole("group", { name: "药品类别" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "项目状态" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "机构角色" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "机构类型" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "机构所在地区" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "研发权益地区" })).toBeInTheDocument();
  fireEvent.click(screen.getByText("临床结果与交易信号"));
  expect(await screen.findByRole("combobox", { name: "是否已有临床结果" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "临床结果评价" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "是否存在交易记录" })).toBeInTheDocument();
  expect(await screen.findByRole("combobox", { name: "交易币种" })).toBeInTheDocument();
});

it("surfaces and retries an authoritative deal facet catalog failure without exposing stale choices", async () => {
  vi.mocked(loadDealFacetCatalog)
    .mockRejectedValueOnce(new Error("Deal facet catalog unavailable"))
    .mockResolvedValueOnce({
      as_of: "2026-07-30T00:00:00Z",
      facets: {
        deal_type: { license: 2 },
        status: { active: 2 },
        direction: { outbound: 2 },
        territory: { Global: 2 },
        asset_modality: { antibody: 2 },
        asset_program_tag: { first_in_class: 2 },
        party_role: { licensor: 2 },
        party_country_region: { US: 2 },
        party_organization_type: { biopharma: 2 },
        development_phase_at_transaction: { phase_2: 2 },
        current_development_phase: { phase_3: 2 },
        right_type: { commercialization: 2 },
        rights_territory: { "Greater China": 2 },
        currency: { USD: 2 },
      },
      warnings: [],
    });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "交易与公司" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("交易筛选选项暂不可用");
  expect(screen.queryByRole("combobox", { name: "交易类型" })).not.toBeInTheDocument();
  fireEvent.click(within(alert).getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("option", { name: "许可 (2)" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "资产模态" })).toBeInTheDocument();
});

it("surfaces and retries an authoritative regulatory facet catalog failure without exposing stale choices", async () => {
  vi.mocked(loadRegulatoryFacetCatalog)
    .mockRejectedValueOnce(new Error("Regulatory facet catalog unavailable"))
    .mockResolvedValueOnce({
      as_of: "2026-07-30T00:00:00Z",
      facets: {
        agency: { FDA: 2 },
        jurisdiction: { US: 2 },
        event_type: { approval: 2 },
        status: { approved: 2 },
        designation_type: { breakthrough_therapy: 2 },
        label_change_type: { initial_label: 2 },
        has_boxed_warning: { true: 2 },
        safety_signal_type: { adverse_event: 2 },
        safety_severity: { serious: 2 },
        safety_status: { confirmed: 2 },
      },
      warnings: [],
    });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "监管与安全" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("监管筛选选项暂不可用");
  expect(screen.queryByRole("combobox", { name: "监管机构" })).not.toBeInTheDocument();
  fireEvent.click(within(alert).getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("option", { name: "FDA (2)" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "事件类型" })).toBeInTheDocument();
});

it("opens a complete epidemiology query from governed facet choices", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "流行病学" }));

  fireEvent.change(await screen.findByRole("combobox", { name: "统计指标" }), {
    target: { value: "prevalence" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "地区" }), { target: { value: "China" } });
  fireEvent.change(screen.getByRole("combobox", { name: "单位" }), { target: { value: "patients" } });
  fireEvent.change(screen.getByRole("combobox", { name: "标准患者人群" }), {
    target: { value: "550e8400-e29b-41d4-a716-446655440003" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "人群口径" }), { target: { value: "adults" } });
  fireEvent.change(screen.getByRole("combobox", { name: "年龄组" }), { target: { value: "18+" } });
  fireEvent.change(screen.getByRole("combobox", { name: "性别" }), { target: { value: "all" } });
  fireEvent.change(screen.getByLabelText("统计周期时间范围"), { target: { value: "custom" } });
  const period = screen.getByRole("group", { name: "统计周期" });
  fireEvent.change(within(period).getByLabelText("起"), { target: { value: "2025-01-01" } });
  fireEvent.change(within(period).getByLabelText("止"), { target: { value: "2025-12-31" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 流行病学" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "epidemiology",
      query: "EGFR",
      epidemiologyMeasure: "prevalence",
      epidemiologyGeography: "China",
      epidemiologyUnit: "patients",
      epidemiologyPatientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
      epidemiologyPopulationScope: "adults",
      epidemiologyAgeGroup: "18+",
      epidemiologySex: "all",
      epidemiologyPeriodStartFrom: "2025-01-01",
      epidemiologyPeriodEndTo: "2025-12-31",
    }),
  );
});

it("surfaces and retries an authoritative epidemiology facet catalog failure without exposing stale choices", async () => {
  vi.mocked(loadEpidemiologyFacetCatalog)
    .mockRejectedValueOnce(new Error("Epidemiology facet catalog unavailable"))
    .mockResolvedValueOnce({
      as_of: "2026-07-30T00:00:00Z",
      facets: {
        measure: { prevalence: 2 },
        geography: { China: 2 },
        unit: { patients: 2 },
        population_scope: { adults: 2 },
        age_group: { "18+": 2 },
        sex: { all: 2 },
      },
      patient_populations: [{ id: "550e8400-e29b-41d4-a716-446655440003", name: "EGFR positive adults", count: 2 }],
      warnings: [],
    });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "流行病学" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("流行病学筛选选项暂不可用");
  expect(screen.queryByRole("combobox", { name: "统计指标" })).not.toBeInTheDocument();
  fireEvent.click(within(alert).getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("option", { name: "患病率 (2)" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "标准患者人群" })).toBeInTheDocument();
});

it("opens a complete news and conference query from governed entities and facets", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "资讯与会议" }));

  fireEvent.change(screen.getByLabelText("关联实体筛选"), { target: { value: "EGFR" } });
  fireEvent.click(await screen.findByRole("option", { name: /EGFR/ }));
  fireEvent.change(await screen.findByRole("combobox", { name: "事件类型" }), {
    target: { value: "conference_abstract" },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "发布方" }), { target: { value: "ASCO" } });
  fireEvent.change(screen.getByRole("combobox", { name: "语言" }), { target: { value: "en" } });
  fireEvent.change(screen.getByRole("combobox", { name: "会议 / 场景" }), { target: { value: "ASCO 2026" } });
  fireEvent.change(screen.getByRole("combobox", { name: "内容范围" }), { target: { value: "research" } });
  fireEvent.change(screen.getByLabelText("发布日期时间范围"), { target: { value: "custom" } });
  const published = screen.getByRole("group", { name: "发布日期" });
  fireEvent.change(within(published).getByLabelText("起"), { target: { value: "2026-07-01" } });
  fireEvent.change(within(published).getByLabelText("止"), { target: { value: "2026-07-31" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 资讯与会议" }));

  expect(onOpenSpecializedSearch).toHaveBeenCalledWith(
    expect.objectContaining({
      view: "news",
      query: "EGFR",
      newsEntityId: "550e8400-e29b-41d4-a716-446655440002",
      newsEventType: "conference_abstract",
      newsPublisher: "ASCO",
      newsLanguage: "en",
      newsVenue: "ASCO 2026",
      newsPublishedFrom: "2026-07-01",
      newsPublishedTo: "2026-07-31",
      newsContentScope: "research",
      newsDisplayMode: "timeline",
    }),
  );
});

it("surfaces and retries an authoritative news facet catalog failure without exposing stale choices", async () => {
  vi.mocked(loadNewsFacetCatalog)
    .mockRejectedValueOnce(new Error("News facet catalog unavailable"))
    .mockResolvedValueOnce({
      as_of: "2026-07-30T00:00:00Z",
      facets: {
        event_type: { conference_abstract: 2 },
        publisher: { ASCO: 2 },
        language: { en: 2 },
        venue: { "ASCO 2026": 2 },
      },
      warnings: [],
    });
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();
  fireEvent.click(screen.getByRole("button", { name: "资讯与会议" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("新闻与会议筛选选项暂不可用");
  expect(screen.queryByRole("combobox", { name: "事件类型" })).not.toBeInTheDocument();
  fireEvent.click(within(alert).getByRole("button", { name: "重试" }));
  expect(await screen.findByRole("option", { name: "会议摘要 (2)" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "会议 / 场景" })).toBeInTheDocument();
});

it.each([
  ["exact", "精确"],
  ["partial", "相关"],
] as const)(
  "prioritizes the original source summary over a duplicated %s canonical-name match in a compact row",
  async (relation, caption) => {
    vi.mocked(searchEntities).mockResolvedValue({
      query_schema_version: "pharma.entity.search.v2",
      applied_filters: [],
      items: [
        {
          ...target,
          match: { ...target.match, match_type: "canonical_name", match_relation: relation, matched_value: "EGFR" },
        },
      ],
      total: 1,
      limit: 100,
      offset: 0,
      sort_by: "relevance",
      sort_direction: "desc",
      facets: {},
      suggestions: [],
      engine: "opensearch",
      took_ms: 12,
    });
    renderWithQueryClient(
      <ExplorerView
        initialQuery="EGFR"
        initialEntityType="target"
        initialReviewStatus="verified"
        onSearchChange={vi.fn()}
        onOpenEntity={vi.fn()}
        onOpenSpecializedSearch={vi.fn()}
      />,
    );
    const table = await screen.findByRole("table", { name: "实体检索结果" });
    const name = within(table).getByRole("button", { name: "EGFR" });
    expect(name.querySelector(".entity-match-context")).toBeNull();
    expect(name.querySelector(".cell-subtitle")).toHaveTextContent("Epidermal growth factor receptor");
    expect(name).toHaveAttribute("aria-description", `名称${caption}匹配：EGFR · Epidermal growth factor receptor`);
  },
);

it("keeps the professional query on the current page when a date range is invalid", async () => {
  const onOpenSpecializedSearch = vi.fn();
  renderWithQueryClient(
    <ExplorerView
      initialQuery="EGFR"
      initialEntityType="target"
      initialReviewStatus="verified"
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenSpecializedSearch={onOpenSpecializedSearch}
    />,
  );
  await screen.findByRole("table", { name: "实体检索结果" });
  openAdvancedQuery();

  fireEvent.change(screen.getByLabelText("状态日期时间范围"), { target: { value: "custom" } });
  const range = screen.getByRole("group", { name: "状态日期" });
  fireEvent.change(within(range).getByLabelText("起"), { target: { value: "2026-12-31" } });
  fireEvent.change(within(range).getByLabelText("止"), { target: { value: "2026-01-01" } });
  fireEvent.click(screen.getByRole("button", { name: "查询 药物与管线" }));

  expect(screen.getByRole("alert")).toHaveTextContent("状态日期起始值不能晚于结束值");
  expect(onOpenSpecializedSearch).not.toHaveBeenCalled();
});
