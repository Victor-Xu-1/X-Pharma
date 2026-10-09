import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";

import {
  type DealSearchFilters,
  emptyDealSearchFilters,
  loadDealDetail,
  saveDealSearch,
  searchDeals,
} from "../lib/contracts/deals";
import { getEntity, lookupEntities, searchEntities } from "../lib/contracts/intelligence";
import { getSessionEntity } from "../lib/contracts/session";
import { setLocale } from "../lib/i18n";
import { DealsView } from "../views/DealsView";
import { dealResult } from "./fixtures/dealResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/deals")>();
  return {
    ...actual,
    searchDeals: vi.fn(),
    loadDealDetail: vi.fn(),
    saveDealSearch: vi.fn(),
  };
});

function renderDeal(overrides: Partial<ComponentProps<typeof DealsView>> = {}) {
  return renderWithQueryClient(
    <DealsView
      displayMode="list"
      analysisDimension="all"
      analysisView="table"
      analysisLimit={8}
      initialFilters={initialFilters}
      initialOffset={0}
      selectedDealId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onAnalysisChange={vi.fn()}
      onDealChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
      {...overrides}
    />,
  );
}

it("renders English deal controls and memoized columns without losing source fields or drafts on switching", async () => {
  act(() => setLocale("en"));
  const onSearchChange = vi.fn();
  renderDeal({ onSearchChange });
  const table = await screen.findByRole("table", { name: "Deal results" });
  expect(within(table).getByRole("columnheader", { name: /Deal name/ })).toBeVisible();
  expect(within(table).getByText("Active", { exact: true })).toBeVisible();
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "未提交交易草稿" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Compare Acme-Beta VX-101 license" }));
  const reads = vi.mocked(searchDeals).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("关键词")).toHaveValue("未提交交易草稿");
  expect(screen.getByRole("checkbox", { name: "取消选择对比 Acme-Beta VX-101 license" })).toBeChecked();
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Keyword")).toHaveValue("未提交交易草稿");
  expect(searchDeals).toHaveBeenCalledTimes(reads);
  expect(onSearchChange).not.toHaveBeenCalled();
});

it("allows an unapplied deal draft to be cleared without treating default sort as an active filter", async () => {
  act(() => setLocale("en"));
  renderDeal({ initialFilters: emptyDealSearchFilters });
  await screen.findByRole("table", { name: "Deal results" });
  expect(screen.getByRole("button", { name: /^Clear$/ })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "draft" } });
  expect(screen.getByRole("button", { name: /^Clear$/ })).toBeEnabled();
});

it("hides cached deal facts and facet counts after a current real-transport permission denial", async () => {
  const { queryClient } = renderDeal();
  await screen.findByRole("table", { name: "交易结果" });
  vi.mocked(searchDeals).mockRejectedValue(new ApiError("RAW_DEAL_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: ["intelligence", "deals"] }));
  expect(await screen.findByRole("alert")).toHaveTextContent("当前账号无权读取这组结果");
  expect(screen.queryByRole("option", { name: "许可 (101)" })).not.toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "交易结果" })).not.toBeInTheDocument();
});

it("rejects a mismatched deal dossier identity", async () => {
  act(() => setLocale("en"));
  vi.mocked(loadDealDetail).mockResolvedValue({ ...dealResult.items[0], id: "foreign-deal" });
  renderDeal({ selectedDealId: dealResult.items[0].id });
  expect(await screen.findByRole("alert")).toHaveTextContent("Deal detail does not match the requested identifier");
  expect(screen.queryByRole("heading", { name: dealResult.items[0].name })).not.toBeInTheDocument();
});

it("retains nested source deal terms instead of flattening them to an object placeholder", async () => {
  act(() => setLocale("en"));
  const terms = {
    royalties: { lower: 0, contingent: false, clauses: ["原始条款 <License>", { region: "SOURCE_REGION" }] },
  };
  vi.mocked(loadDealDetail).mockResolvedValue({ ...dealResult.items[0], terms });
  renderDeal({ selectedDealId: dealResult.items[0].id, activeSection: "terms" });
  expect(await screen.findByRole("heading", { name: dealResult.items[0].name })).toBeVisible();
  fireEvent.click(screen.getByText("Complete source metadata", { exact: true }));
  expect(document.querySelector(".source-metadata pre")?.textContent).toBe(JSON.stringify(terms, null, 2));
  expect(document.body).not.toHaveTextContent("[object Object]");
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

const initialFilters: DealSearchFilters = { ...emptyDealSearchFilters, query: "VX-101" };

beforeEach(() => {
  vi.mocked(searchDeals).mockResolvedValue(dealResult);
  vi.mocked(loadDealDetail).mockResolvedValue(dealResult.items[0]);
  vi.mocked(saveDealSearch).mockResolvedValue({ kind: "saved", monitoring: true });
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
  expect(screen.getByRole("group", { name: "交易药品检索与选择", hidden: true }).closest("details")).toBe(participants);
  expect(screen.getByRole("group", { name: "关联靶点检索与选择", hidden: true }).closest("details")).toBe(participants);
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
  expect(screen.getByText("USD 25,000,000")).toBeInTheDocument();
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
