import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  type DealSearchFilters,
  emptyDealSearchFilters,
  loadDealDetail,
  saveDealSearch,
  searchDeals,
} from "../lib/contracts/deals";
import { getEntity, lookupEntities, searchEntities } from "../lib/contracts/intelligence";
import { getSessionEntity } from "../lib/contracts/session";
import { DealsView } from "../views/DealsView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/deals")>();
  return {
    ...actual,
    dealKeys: {
      search: (filters: DealSearchFilters, offset: number, analysisLimit: number) => [
        "deals",
        { ...filters, offset, analysisLimit },
      ],
      detail: (dealId: string) => ["deals", "detail", dealId],
    },
    searchDeals: vi.fn(),
    loadDealDetail: vi.fn(),
    saveDealSearch: vi.fn(),
  };
});

vi.mock("../lib/contracts/intelligence", () => ({
  intelligenceKeys: {
    search: (query: string, entityType: string, reviewStatus: string) => [
      "entities",
      { query, entityType, reviewStatus },
    ],
    lookup: (query: string, entityType: string) => ["entity-lookup", { query, entityType }],
    entity: (entityId: string) => ["entity", entityId],
  },
  searchEntities: vi.fn(),
  lookupEntities: vi.fn(),
  getEntity: vi.fn(),
}));

vi.mock("../lib/contracts/session", () => ({
  sessionKeys: { entity: (entityId: string) => ["entity", entityId] },
  getSessionEntity: vi.fn(),
}));

const dealResult = {
  items: [
    {
      id: "550e8400-e29b-41d4-a716-446655440010",
      entity_id: "550e8400-e29b-41d4-a716-446655440001",
      name: "Acme-Beta VX-101 license",
      deal_type: "license",
      status: "active" as const,
      direction: "outbound" as const,
      direction_reference_jurisdiction: "US",
      announced_at: "2026-01-20T00:00:00Z",
      terminated_at: null,
      source_updated_at: "2026-03-15T00:00:00Z",
      parties: [],
      asset_entity_ids: ["550e8400-e29b-41d4-a716-446655440004"],
      territory: "global",
      upfront_amount: 25_000_000,
      total_potential_amount: 500_000_000,
      currency: "USD",
      terms: { royalties: "tiered" },
      source_document_id: "source-1",
      party_entities: [
        { id: "550e8400-e29b-41d4-a716-446655440002", name: "Acme Pharma", entity_type: "organization" as const },
        { id: "550e8400-e29b-41d4-a716-446655440003", name: "Beta Bio", entity_type: "organization" as const },
      ],
      asset_entities: [{ id: "550e8400-e29b-41d4-a716-446655440004", name: "VX-101", entity_type: "drug" as const }],
      party_roles: [
        {
          id: "550e8400-e29b-41d4-a716-446655440002",
          name: "Acme Pharma",
          entity_type: "organization" as const,
          role: "licensor" as const,
          country_region: "US",
          organization_type: "biopharma",
        },
        {
          id: "550e8400-e29b-41d4-a716-446655440003",
          name: "Beta Bio",
          entity_type: "organization" as const,
          role: "licensee" as const,
          country_region: "China",
          organization_type: "biotech",
        },
      ],
      asset_stages: [
        {
          id: "550e8400-e29b-41d4-a716-446655440004",
          name: "VX-101",
          entity_type: "drug" as const,
          development_phase_at_transaction: "phase_2",
          current_development_phase: "phase_3",
          current_phase_as_of: "2026-07-01T00:00:00Z",
        },
      ],
      rights: [
        {
          id: "right-1",
          holder_entity_id: "550e8400-e29b-41d4-a716-446655440003",
          holder_name: "Beta Bio",
          right_type: "commercialization" as const,
          territory: "Greater China",
          exclusive: true,
          scope_description: "Exclusive commercialization rights",
          source_document_id: "source-1",
        },
      ],
    },
  ],
  total: 101,
  limit: 100,
  offset: 0,
  facets: {
    deal_type: { license: 101 },
    status: { active: 101 },
    direction: { outbound: 101 },
    territory: { global: 101 },
    currency: { USD: 101 },
    asset: { "VX-101": 101 },
    target: { EGFR: 101 },
    disease: { "Lung cancer": 101 },
    asset_modality: { antibody: 71, "small molecule": 30 },
    asset_program_tag: { first_in_class: 61, best_in_class: 40 },
    party: { "Acme Pharma": 101, "Beta Bio": 101 },
    party_role: { licensor: 101, licensee: 101 },
    party_country_region: { US: 101, China: 101 },
    party_organization_type: { biopharma: 101, biotech: 101 },
    development_phase_at_transaction: { phase_2: 101 },
    current_development_phase: { phase_3: 101 },
    right_type: { commercialization: 101 },
    rights_territory: { "Greater China": 101 },
  },
  landscape: {
    total_deals: 101,
    limit: 8 as const,
    deal_type: [{ key: "license", label: "license", count: 101, share: 1 }],
    status: [{ key: "active", label: "active", count: 101, share: 1 }],
    direction: [{ key: "outbound", label: "outbound", count: 101, share: 1 }],
    territory: [{ key: "global", label: "global", count: 101, share: 1 }],
    currency: [{ key: "USD", label: "USD", count: 101, share: 1 }],
    asset_modality: [
      { key: "antibody", label: "antibody", count: 71, share: 0.70297 },
      { key: "small molecule", label: "small molecule", count: 30, share: 0.29703 },
    ],
    transaction_phase: [{ key: "phase_2", label: "phase_2", count: 101, share: 1 }],
    current_phase: [{ key: "phase_3", label: "phase_3", count: 101, share: 1 }],
    party_country: [
      { key: "US", label: "US", count: 101, share: 1 },
      { key: "China", label: "China", count: 101, share: 1 },
    ],
    rights_territory: [{ key: "Greater China", label: "Greater China", count: 101, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  query_schema_version: "pharma.deal.search.v8",
  sort_by: "announced_at" as const,
  sort_direction: "desc" as const,
  applied_filters: [{ field: "q", operator: "contains" as const, value: "VX-101" }],
  warnings: ["未观察到交易不代表不存在；结果受数据授权、披露完整性、金额口径和治理状态限制。"],
};

const initialFilters: DealSearchFilters = { ...emptyDealSearchFilters, query: "VX-101" };

beforeEach(() => {
  vi.mocked(searchDeals).mockResolvedValue(dealResult);
  vi.mocked(loadDealDetail).mockResolvedValue(dealResult.items[0]);
  vi.mocked(saveDealSearch).mockResolvedValue({ message: "交易检索已保存并启用监控" });
  vi.mocked(searchEntities).mockResolvedValue({
    query_schema_version: "pharma.entity.search.v2",
    applied_filters: [],
    items: [
      {
        id: "550e8400-e29b-41d4-a716-446655440002",
        entity_type: "organization",
        name: "Acme Pharma",
        canonical_entity_id: "550e8400-e29b-41d4-a716-446655440002",
        external_ids: { lei: "ACME-01" },
        description: null,
        attributes: {},
        review_status: "verified",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
    total: 1,
    limit: 100,
    offset: 0,
    sort_by: "relevance",
    sort_direction: "desc",
    engine: "opensearch",
    facets: {},
    suggestions: [],
    took_ms: 3,
  });
  vi.mocked(getSessionEntity).mockResolvedValue({
    id: "550e8400-e29b-41d4-a716-446655440002",
    entity_type: "organization",
    name: "Acme Pharma",
    canonical_entity_id: "550e8400-e29b-41d4-a716-446655440002",
    external_ids: {},
    description: null,
    attributes: {},
    review_status: "verified",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  });
  const entityByType = {
    drug: {
      id: "550e8400-e29b-41d4-a716-446655440004",
      entity_type: "drug" as const,
      name: "VX-101",
    },
    target: {
      id: "550e8400-e29b-41d4-a716-446655440005",
      entity_type: "target" as const,
      name: "EGFR",
    },
    disease: {
      id: "550e8400-e29b-41d4-a716-446655440006",
      entity_type: "disease" as const,
      name: "Lung cancer",
    },
  };
  vi.mocked(lookupEntities).mockImplementation(async (_query, entityType) => {
    const entity = entityByType[entityType as keyof typeof entityByType];
    return entity
      ? [
          {
            ...entity,
            canonical_entity_id: entity.id,
            external_ids: {},
            description: null,
            attributes: {},
            review_status: "verified",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]
      : [];
  });
  vi.mocked(getEntity).mockImplementation(async (entityId) => {
    const entity = Object.values(entityByType).find((item) => item.id === entityId);
    if (!entity) throw new Error("Entity not found");
    return {
      ...entity,
      canonical_entity_id: entity.id,
      external_ids: {},
      description: null,
      attributes: {},
      review_status: "verified",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
  });
});

function renderDeals(overrides: Partial<Parameters<typeof DealsView>[0]> = {}) {
  const props = {
    displayMode: "list" as const,
    analysisDimension: "all" as const,
    analysisView: "chart" as const,
    analysisLimit: 8 as const,
    initialFilters,
    initialOffset: 0,
    selectedDealId: null,
    activeSection: "overview" as const,
    onSearchChange: vi.fn(),
    onDisplayModeChange: vi.fn(),
    onAnalysisChange: vi.fn(),
    onDealChange: vi.fn(),
    onSectionChange: vi.fn(),
    onOpenEntity: vi.fn(),
    onOpenDrug: vi.fn(),
    onOpenTarget: vi.fn(),
    onOpenDisease: vi.fn(),
    onOpenOrganization: vi.fn(),
    ...overrides,
  };
  renderWithQueryClient(<DealsView {...props} />);
  return props;
}

it("keeps common deal filters first and leaves unused participant conditions collapsed", async () => {
  renderDeals();
  await screen.findByRole("table", { name: "交易结果" });
  const participants = screen.getByText("参与方与关联条件").closest("details");
  expect(participants).not.toHaveAttribute("open");
  expect(screen.getByLabelText("交易方向").closest("details")).toBe(participants);
  expect(screen.getByLabelText("参与机构").closest("details")).toBe(participants);
  expect(screen.getByLabelText("参与角色").closest("details")).toBe(participants);
  expect(screen.getByRole("group", { name: "关联适应症检索与选择", hidden: true }).closest("details")).toBe(
    participants,
  );
  expect(screen.getByRole("group", { name: "交易药品检索与选择" }).closest("details")).toBeNull();
  expect(screen.getByRole("group", { name: "关联靶点检索与选择" }).closest("details")).toBeNull();
});

it("reveals restored participant conditions and counts a selected organization only once", async () => {
  const props = renderDeals({
    initialFilters: {
      ...initialFilters,
      party: "Acme Pharma",
      partyEntityId: "550e8400-e29b-41d4-a716-446655440002",
      partyRole: "licensor",
      direction: "outbound",
      directionReferenceJurisdiction: "US",
    },
  });
  await screen.findByRole("table", { name: "交易结果" });
  const participants = screen.getByText("参与方与关联条件").closest("details");
  expect(participants).toHaveAttribute("open");
  expect(participants).toHaveTextContent("已选 3 项");
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(props.onSearchChange).toHaveBeenCalledWith(
    expect.objectContaining({
      party: "Acme Pharma",
      partyEntityId: "550e8400-e29b-41d4-a716-446655440002",
      partyRole: "licensor",
      direction: "outbound",
    }),
    0,
  );
});

it("reveals restored advanced conditions including zero amount values", async () => {
  renderDeals({
    initialFilters: {
      ...initialFilters,
      currency: "USD",
      upfrontAmountMin: "0",
      assetModalities: ["antibody", "small molecule"],
    },
  });
  await screen.findByRole("table", { name: "交易结果" });
  const advanced = screen.getByText("更多交易条件").closest("details");
  expect(advanced).toHaveAttribute("open");
  expect(advanced).toHaveTextContent("已选 3 项");
  expect(screen.getByLabelText("币种")).toHaveValue("USD");
});

it("renders governed role, stage, rights and dense deal results", async () => {
  const props = renderDeals();

  expect(await screen.findByRole("table", { name: "交易结果" })).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|数据授权/);
  expect(searchDeals).toHaveBeenCalledWith(initialFilters, 0, 8, expect.any(AbortSignal));
  expect(screen.getByText("许可方")).toBeInTheDocument();
  expect(screen.getByText("II期 → 当前 III期")).toBeInTheDocument();
  expect(screen.getByText("商业化 · Greater China")).toBeInTheDocument();
  expect(screen.getByText("USD 25.0M")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "已应用查询条件" })).toHaveTextContent("关键词VX-101");

  fireEvent.click(screen.getByRole("button", { name: /Acme Pharma许可方/ }));
  expect(props.onOpenOrganization).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  fireEvent.click(screen.getByRole("button", { name: /VX-101II期/ }));
  expect(props.onOpenDrug).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440004");
  fireEvent.click(screen.getByText("Acme-Beta VX-101 license").closest("button") as HTMLButtonElement);
  expect(props.onDealChange).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440010");
  const dossierButton = screen
    .getAllByRole("button")
    .find((button) => button.getAttribute("aria-label")?.includes("Acme-Beta VX-101 license"));
  if (!dossierButton) throw new Error("deal dossier button not found");
  fireEvent.click(dossierButton);
  expect(props.onDealChange).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440010");
});

it("submits role-aware advanced filters with a stable organization id", async () => {
  const props = renderDeals({
    initialFilters: {
      ...initialFilters,
      assetEntityId: "550e8400-e29b-41d4-a716-446655440004",
      targetEntityId: "550e8400-e29b-41d4-a716-446655440005",
      diseaseEntityId: "550e8400-e29b-41d4-a716-446655440006",
    },
  });
  await screen.findByRole("table", { name: "交易结果" });

  fireEvent.change(screen.getByLabelText("交易类型"), { target: { value: "license" } });
  fireEvent.change(screen.getByLabelText("交易状态"), { target: { value: "active" } });
  fireEvent.change(screen.getByLabelText("交易方向"), { target: { value: "outbound" } });
  fireEvent.change(screen.getByLabelText("参与机构"), { target: { value: "Acme" } });
  fireEvent.click(await screen.findByRole("option", { name: /Acme Pharma/ }));
  fireEvent.change(screen.getByLabelText("参与角色"), { target: { value: "licensor" } });
  fireEvent.click(screen.getByText("更多交易条件"));
  fireEvent.change(screen.getByLabelText("方向参照地区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("机构所在地区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("机构类型"), { target: { value: "biopharma" } });
  fireEvent.click(screen.getByLabelText("资产模态：全部"));
  fireEvent.click(screen.getByRole("checkbox", { name: /antibody/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /small molecule/ }));
  fireEvent.click(screen.getByLabelText("资产项目标签：全部"));
  fireEvent.click(screen.getByRole("checkbox", { name: /first_in_class/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /best_in_class/ }));
  fireEvent.change(screen.getByLabelText("交易时阶段"), { target: { value: "phase_2" } });
  fireEvent.change(screen.getByLabelText("当前最高阶段"), { target: { value: "phase_3" } });
  fireEvent.change(screen.getByLabelText("权益类型"), { target: { value: "commercialization" } });
  fireEvent.change(screen.getByLabelText("权益地区"), { target: { value: "Greater China" } });
  const announcedRange = within(screen.getByRole("group", { name: "初始披露" }));
  fireEvent.change(announcedRange.getByLabelText("起"), { target: { value: "2026-01-01" } });
  fireEvent.change(announcedRange.getByLabelText("止"), { target: { value: "2026-12-31" } });
  const upfrontRange = within(screen.getByRole("group", { name: "首付款" }));
  fireEvent.change(upfrontRange.getByLabelText("下限"), { target: { value: "10000000" } });
  fireEvent.change(upfrontRange.getByLabelText("上限"), { target: { value: "30000000" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));

  await waitFor(() => expect(props.onSearchChange).toHaveBeenCalledTimes(1));
  const submitted = vi.mocked(props.onSearchChange).mock.calls[0][0];
  expect(submitted).toMatchObject({
    query: "VX-101",
    dealType: "license",
    status: "active",
    direction: "outbound",
    directionReferenceJurisdiction: "US",
    assetEntityId: "550e8400-e29b-41d4-a716-446655440004",
    targetEntityId: "550e8400-e29b-41d4-a716-446655440005",
    diseaseEntityId: "550e8400-e29b-41d4-a716-446655440006",
    party: "Acme Pharma",
    partyEntityId: "550e8400-e29b-41d4-a716-446655440002",
    partyRole: "licensor",
    partyCountryRegion: "US",
    partyOrganizationType: "biopharma",
    assetModalities: ["antibody", "small molecule"],
    assetProgramTags: ["first_in_class", "best_in_class"],
    developmentPhaseAtTransaction: "phase_2",
    currentDevelopmentPhase: "phase_3",
    rightType: "commercialization",
    rightsTerritory: "Greater China",
    announcedFrom: "2026-01-01",
    announcedTo: "2026-12-31",
    upfrontAmountMin: "10000000",
    upfrontAmountMax: "30000000",
  });
  expect(vi.mocked(props.onSearchChange).mock.calls[0][1]).toBe(0);
});

it("opens a stable deal professional dossier and navigates governed relationships", async () => {
  const props = renderDeals({
    selectedDealId: "550e8400-e29b-41d4-a716-446655440010",
    activeSection: "rights",
  });
  await screen.findByRole("heading", { name: "Acme-Beta VX-101 license" });
  expect(loadDealDetail).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440010", expect.any(AbortSignal));
  expect(searchDeals).not.toHaveBeenCalled();
  expect(screen.getByText(/交易专业档案/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "地域权益" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "交易权益明细" })).toHaveAttribute("tabindex", "0");
  expect(screen.getByText("Exclusive commercialization rights")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Beta Bio" }));
  expect(props.onOpenOrganization).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440003");
  fireEvent.click(screen.getByRole("tab", { name: "资产与阶段" }));
  expect(props.onSectionChange).toHaveBeenCalledWith("assets");
  fireEvent.click(screen.getByRole("button", { name: "返回交易列表" }));
  expect(props.onDealChange).toHaveBeenCalledWith(null);
});

it("validates amount ranges and clears all filters", async () => {
  const invalid = renderDeals();
  await screen.findByRole("table", { name: "交易结果" });
  fireEvent.click(screen.getByText("更多交易条件"));
  const totalRange = within(screen.getByRole("group", { name: "潜在总额" }));
  fireEvent.change(totalRange.getByLabelText("下限"), { target: { value: "600000000" } });
  fireEvent.change(totalRange.getByLabelText("上限"), { target: { value: "500000000" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(screen.getByRole("alert")).toHaveTextContent("潜在总额下限不能高于上限");
  expect(invalid.onSearchChange).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() => expect(invalid.onSearchChange).toHaveBeenCalledWith(emptyDealSearchFilters, 0));
});

it("renders an explicit empty state", async () => {
  vi.mocked(searchDeals).mockResolvedValue({
    ...dealResult,
    items: [],
    applied_filters: [{ field: "deal_type", operator: "eq", value: "license" }],
    total: 0,
    facets: {},
    landscape: { ...dealResult.landscape, total_deals: 0, deal_type: [], status: [], direction: [] },
  });
  renderDeals({ initialFilters: { ...initialFilters, dealType: "license" } });
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  expect(screen.getByRole("dialog", { name: "保存当前交易检索" })).toBeVisible();
});

it("saves and subscribes the applied deal query rather than an unsent draft", async () => {
  renderDeals();
  await screen.findByRole("table", { name: "交易结果" });
  fireEvent.change(screen.getByLabelText("关键词"), { target: { value: "unsent draft" } });
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "VX-101 deal watch" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(saveDealSearch).toHaveBeenCalledWith(
      {
        name: "VX-101 deal watch",
        filters: initialFilters,
        displayMode: "list",
        analysis: { dimension: "all", view: "chart", limit: 8 },
        shared: false,
        monitor: true,
      },
      expect.any(Object),
    ),
  );
  expect(await screen.findByText("交易检索已保存并启用监控")).toBeVisible();
});

it("renders full-result deal statistics and drills a governed bucket back into the query", async () => {
  const props = renderDeals({
    displayMode: "landscape",
    analysisDimension: "status",
    analysisView: "table",
  });

  const table = await screen.findByRole("table", { name: "交易状态统计表" });
  expect(screen.getByRole("region", { name: "交易数据统计" })).toBeInTheDocument();
  expect(within(table).getByText("进行中")).toBeInTheDocument();
  fireEvent.click(within(table).getByRole("button", { name: "筛选" }));
  expect(props.onSearchChange).toHaveBeenCalledWith({ ...initialFilters, status: "active" }, 0);

  fireEvent.change(screen.getByLabelText("交易分析维度"), { target: { value: "asset_modality" } });
  expect(props.onAnalysisChange).toHaveBeenCalledWith({ dimension: "asset_modality", view: "table", limit: 8 });
  fireEvent.click(screen.getByRole("button", { name: "列表" }));
  expect(props.onDisplayModeChange).toHaveBeenCalledWith("list");
});

it("renders a recoverable query error", async () => {
  vi.mocked(searchDeals).mockRejectedValue(new Error("Deal source unavailable"));
  renderDeals();
  expect(await screen.findByText("Deal source unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("requests a full-result deal sort from a sortable header", async () => {
  const props = renderDeals();
  const table = await screen.findByRole("table");
  const nameHeader = within(table)
    .getAllByRole("columnheader")
    .find((header) => header.textContent?.includes("交易名称"));
  if (!nameHeader) throw new Error("deal name column header not found");
  fireEvent.click(within(nameHeader).getByRole("button"));

  expect(props.onSearchChange).toHaveBeenCalledWith(
    {
      ...initialFilters,
      sortBy: "name",
      sortDirection: "asc",
      sort: [{ field: "name", direction: "asc" }],
    },
    0,
  );
});
