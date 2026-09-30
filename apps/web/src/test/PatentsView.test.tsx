import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { getEntity } from "../lib/contracts/intelligence";
import { loadPatentFamilyDetail, savePatentSearch, searchPatentFamilies } from "../lib/contracts/patents";
import { PatentsView } from "../views/PatentsView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/patents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/patents")>();
  return {
    ...actual,
    patentKeys: {
      search: (...args: unknown[]) => ["patents", args],
      detail: (familyId: string) => ["patents", "detail", familyId],
    },
    loadPatentFamilyDetail: vi.fn(),
    savePatentSearch: vi.fn(),
    searchPatentFamilies: vi.fn(),
  };
});
vi.mock("../lib/contracts/intelligence", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/intelligence")>();
  return { ...actual, getEntity: vi.fn(), lookupEntities: vi.fn() };
});

const patentResult = {
  items: [
    {
      id: "patent-1",
      entity_id: "550e8400-e29b-41d4-a716-446655440001",
      family_identifier: "INPADOC-123456",
      title: "EGFR kinase inhibitors for treating NSCLC",
      priority_date: "2021-02-03",
      applicants: ["Victor Therapeutics"],
      inventors: ["Wei Chen", "Lin Zhang"],
      publications: [{ publication_number: "WO2022123456A1" }],
      legal_status: "ACTIVE",
      legal_status_at: "2026-06-01T00:00:00Z",
      legal_events: [
        {
          event_type: "grant",
          status: "ACTIVE",
          occurred_at: "2026-06-01T00:00:00Z",
          jurisdiction: "WO",
          publication_number: "WO2022123456A1",
        },
      ],
      independent_claims: [
        {
          claim_number: "1",
          claim_type: "composition" as const,
          summary: "Composition covering an EGFR kinase inhibitor.",
        },
      ],
      expiration_date: "2042-02-03",
      linked_entity_ids: ["550e8400-e29b-41d4-a716-446655440002"],
      source_document_id: null,
      linked_entities: [{ id: "550e8400-e29b-41d4-a716-446655440002", name: "EGFR", entity_type: "target" as const }],
    },
  ],
  total: 101,
  limit: 100,
  offset: 0,
  query_schema_version: "pharma.patent.search.v2",
  applied_filters: [],
  sort_by: "priority_date" as const,
  sort_direction: "desc" as const,
  facets: {
    applicant: { "Victor Therapeutics": 101 },
    legal_status: { ACTIVE: 101 },
  },
  landscape: {
    total_families: 101,
    legal_status: [{ key: "ACTIVE", label: "ACTIVE", count: 101, share: 1 }],
    top_applicants: [{ key: "Victor Therapeutics", label: "Victor Therapeutics", count: 101, share: 1 }],
    priority_year: [{ key: "2024", label: "2024", count: 101, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  warnings: ["结果受当前数据授权、法律状态时效和治理状态限制。"],
};

beforeEach(() => {
  vi.mocked(searchPatentFamilies).mockResolvedValue(patentResult);
  vi.mocked(loadPatentFamilyDetail).mockResolvedValue(patentResult.items[0]);
  vi.mocked(savePatentSearch).mockResolvedValue({ message: "专利检索已保存并启用监控" });
  vi.mocked(getEntity).mockResolvedValue({
    id: "550e8400-e29b-41d4-a716-446655440099",
    canonical_entity_id: "550e8400-e29b-41d4-a716-446655440099",
    entity_type: "drug",
    name: "Restored patent drug",
    description: "",
    external_ids: {},
    attributes: {},
    review_status: "verified",
    created_at: "2026-07-30T00:00:00Z",
    updated_at: "2026-07-30T00:00:00Z",
  });
});

it("restores the governed type of a linked non-target entity", async () => {
  renderWithQueryClient(
    <PatentsView
      initialQuery="EGFR"
      initialEntityId="550e8400-e29b-41d4-a716-446655440099"
      initialApplicant=""
      initialLegalStatus=""
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="priority_date"
      initialSortDirection="desc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onPatentChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  await waitFor(() => expect(screen.getByLabelText("关联实体类型")).toHaveValue("drug"));
  expect(await screen.findByText("Restored patent drug")).toBeVisible();
});

it("renders governed patent intelligence, filters it and opens linked dossiers", async () => {
  const onSearchChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  const onPatentChange = vi.fn();
  renderWithQueryClient(
    <PatentsView
      initialQuery="EGFR"
      initialEntityId=""
      initialApplicant=""
      initialLegalStatus=""
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="priority_date"
      initialSortDirection="desc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={onSearchChange}
      onPatentChange={onPatentChange}
      onSectionChange={vi.fn()}
      onOpenEntity={onOpenEntity}
      onOpenDrug={onOpenDrug}
      onOpenTarget={onOpenTarget}
      onOpenDisease={onOpenDisease}
      onOpenOrganization={onOpenOrganization}
    />,
  );

  expect(await screen.findByRole("table", { name: "专利族结果" })).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|授权来源/);
  expect(screen.getByText(/全部结果按最早优先权降序/)).toBeInTheDocument();
  expect(searchPatentFamilies).toHaveBeenCalledWith(
    expect.objectContaining({ query: "EGFR", sortBy: "priority_date", sortDirection: "desc" }),
    0,
    expect.any(AbortSignal),
  );
  expect(screen.getByText("INPADOC-123456")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "打开专利族详情：INPADOC-123456" }));
  expect(onPatentChange).toHaveBeenCalledWith("patent-1");
  expect(screen.getByText("有效")).toBeInTheDocument();
  fireEvent.click(screen.getByText("1 个事件 · 1 项独立权利要求"));
  expect(screen.getByText("Composition covering an EGFR kinase inhibitor.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  fireEvent.click(screen.getByRole("button", { name: "打开 INPADOC-123456 档案" }));
  expect(onPatentChange).toHaveBeenLastCalledWith("patent-1");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(within(screen.getByRole("columnheader", { name: /专利族与标题/ })).getByRole("button"));
  const lastSortCall = onSearchChange.mock.calls.at(-1);
  expect(lastSortCall?.[0]).toMatchObject({ sortBy: "family_identifier", sortDirection: "asc" });
  expect(lastSortCall?.[1]).toBe(0);

  fireEvent.change(screen.getByLabelText("申请人"), { target: { value: "Victor Therapeutics" } });
  fireEvent.change(screen.getByLabelText("法律状态"), { target: { value: "ACTIVE" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(onSearchChange).toHaveBeenCalledWith(
    {
      query: "EGFR",
      entityId: "",
      applicant: "Victor Therapeutics",
      legalStatus: "ACTIVE",
      priorityFrom: "",
      priorityTo: "",
      expirationFrom: "",
      expirationTo: "",
      sortBy: "priority_date",
      sortDirection: "desc",
      displayMode: "list",
      analysisView: "chart",
    },
    0,
  );

  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenCalledWith(
    expect.objectContaining({ query: "EGFR", sortBy: "priority_date", sortDirection: "desc" }),
    100,
  );
});

it("renders the explicit patent empty state and clears active filters", async () => {
  vi.mocked(searchPatentFamilies).mockResolvedValue({
    ...patentResult,
    items: [],
    total: 0,
    facets: {},
    landscape: { total_families: 0, legal_status: [], top_applicants: [], priority_year: [] },
  });
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <PatentsView
      initialQuery="missing"
      initialEntityId=""
      initialApplicant="Victor Therapeutics"
      initialLegalStatus="ACTIVE"
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="priority_date"
      initialSortDirection="desc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={onSearchChange}
      onPatentChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("未观察到匹配专利族")).toBeInTheDocument();
  expect(screen.getByText("可调整关键词、申请人、辖区、法律状态或日期条件后重试。")).toBeInTheDocument();
  expect(screen.getByPlaceholderText("输入药品、靶点、适应症或机构")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/规范药物|输入规范实体/);
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  expect(screen.getByRole("dialog", { name: "保存当前专利检索" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() =>
    expect(onSearchChange).toHaveBeenCalledWith(
      expect.objectContaining({ query: "", applicant: "", legalStatus: "", entityId: "" }),
      0,
    ),
  );
});

it("saves and subscribes the applied patent query", async () => {
  renderWithQueryClient(
    <PatentsView
      initialQuery="EGFR"
      initialEntityId=""
      initialApplicant="Victor Therapeutics"
      initialLegalStatus="ACTIVE"
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="family_identifier"
      initialSortDirection="asc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onPatentChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "专利族结果" });
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "EGFR active patents" } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(savePatentSearch).toHaveBeenCalledWith(
      {
        name: "EGFR active patents",
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
          displayMode: "list",
          analysisView: "chart",
        },
        shared: true,
        monitor: true,
      },
      expect.any(Object),
    ),
  );
  expect(await screen.findByText("专利检索已保存并启用监控")).toBeVisible();
});

it("renders a recoverable patent query error", async () => {
  vi.mocked(searchPatentFamilies).mockRejectedValue(new Error("Patent registry unavailable"));
  renderWithQueryClient(
    <PatentsView
      initialQuery=""
      initialEntityId=""
      initialApplicant=""
      initialLegalStatus=""
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="priority_date"
      initialSortDirection="desc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onPatentChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("Patent registry unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("loads a stable patent-family detail and closes it through controlled URL state", async () => {
  vi.mocked(loadPatentFamilyDetail).mockResolvedValueOnce({ ...patentResult.items[0], linked_entities: [] });
  const onPatentChange = vi.fn();
  renderWithQueryClient(
    <PatentsView
      initialQuery=""
      initialEntityId=""
      initialApplicant=""
      initialLegalStatus=""
      initialPriorityFrom=""
      initialPriorityTo=""
      initialExpirationFrom=""
      initialExpirationTo=""
      initialSortBy="priority_date"
      initialSortDirection="desc"
      initialOffset={0}
      displayMode="list"
      analysisView="chart"
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      selectedPatentId="patent-1"
      activeSection="relationships"
      onSearchChange={vi.fn()}
      onPatentChange={onPatentChange}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  const dossier = await screen.findByRole("heading", { name: patentResult.items[0].title });
  expect(loadPatentFamilyDetail).toHaveBeenCalledWith("patent-1", expect.any(AbortSignal));
  expect(searchPatentFamilies).not.toHaveBeenCalled();
  expect(screen.getByText("专利族专业档案 · INPADOC-123456")).toBeInTheDocument();
  expect(screen.getByText("暂无关联实体信息")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|授权来源/);
  fireEvent.click(within(dossier.closest("section") as HTMLElement).getByRole("button", { name: "返回专利族列表" }));
  expect(onPatentChange).toHaveBeenCalledWith(null);
});
