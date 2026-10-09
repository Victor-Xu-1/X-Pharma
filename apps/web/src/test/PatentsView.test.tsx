import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";

import { getEntity } from "../lib/contracts/intelligence";
import { loadPatentFamilyDetail, savePatentSearch, searchPatentFamilies } from "../lib/contracts/patents";
import type { SavedSearchCreationOutcome } from "../lib/contracts/savedSearchCreation";
import { setLocale } from "../lib/i18n";
import { PatentsView } from "../views/PatentsView";
import { patentResult } from "./fixtures/patentsResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/patents", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/patents")>();
  return {
    ...actual,
    loadPatentFamilyDetail: vi.fn(),
    savePatentSearch: vi.fn(),
    searchPatentFamilies: vi.fn(),
  };
});

function renderPatent(overrides: Partial<ComponentProps<typeof PatentsView>> = {}) {
  return renderWithQueryClient(
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
      selectedPatentId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onAnalysisViewChange={vi.fn()}
      onPatentChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
      {...overrides}
    />,
  );
}

it("renders English patent filters and memoized columns while retaining drafts and selection on switching", async () => {
  act(() => setLocale("en"));
  const onSearchChange = vi.fn();
  renderPatent({ onSearchChange, initialQuery: "EGFR" });
  const table = await screen.findByRole("table", { name: "Patent family results" });
  expect(within(table).getByRole("columnheader", { name: /Family and title/ })).toBeVisible();
  expect(screen.getByLabelText("Legal status")).toBeVisible();
  expect(screen.getByLabelText("Applicant")).toHaveAttribute("aria-label", "Applicant");
  expect(screen.getByLabelText("Legal status")).toHaveAttribute("aria-label", "Legal status");
  expect(screen.getByText("1 events · 1 independent claims")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "EGFR 未提交" } });
  expect(within(table).getByText("Active", { exact: true })).toBeVisible();
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Compare INPADOC-123456" }));
  const reads = vi.mocked(searchPatentFamilies).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("关键词")).toHaveValue("EGFR 未提交");
  expect(screen.getByRole("checkbox", { name: "取消选择对比 INPADOC-123456" })).toBeChecked();
  expect(screen.getByRole("columnheader", { name: /专利族与标题/ })).toBeVisible();
  expect(screen.getByLabelText("申请人")).toHaveAttribute("aria-label", "申请人");
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Keyword")).toHaveValue("EGFR 未提交");
  expect(screen.getByRole("checkbox", { name: "Deselect Compare INPADOC-123456" })).toBeChecked();
  expect(searchPatentFamilies).toHaveBeenCalledTimes(reads);
  expect(onSearchChange).not.toHaveBeenCalled();
  expect(screen.getByText("EGFR kinase inhibitors for treating NSCLC")).toBeVisible();
});

it("keeps date-only and unapplied patent filters clearable without treating default sort as a filter", async () => {
  act(() => setLocale("en"));
  const onSearchChange = vi.fn();
  renderPatent({ onSearchChange, initialPriorityFrom: "2021-02-03" });
  await screen.findByRole("table", { name: "Patent family results" });
  expect(screen.getByRole("button", { name: "Clear" })).toBeEnabled();
  expect(screen.getByText("More patent conditions").closest("details")).toHaveAttribute("open");
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(onSearchChange).toHaveBeenCalledWith(expect.objectContaining({ priorityFrom: "", priorityTo: "" }), 0);
});

it("clears an unapplied draft and validates reversed patent date ranges before applying", async () => {
  act(() => setLocale("en"));
  const onSearchChange = vi.fn();
  renderPatent({ onSearchChange });
  await screen.findByRole("table", { name: "Patent family results" });
  expect(screen.getByRole("button", { name: "Clear" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "draft" } });
  expect(screen.getByRole("button", { name: "Clear" })).toBeEnabled();
  fireEvent.click(screen.getByText("More patent conditions"));
  const dates = within(screen.getByRole("group", { name: "Priority dates" }));
  fireEvent.change(dates.getByLabelText("From"), { target: { value: "2026-03-01" } });
  fireEvent.change(dates.getByLabelText("To"), { target: { value: "2026-02-01" } });
  fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("Priority start date cannot be later than its end date");
  expect(onSearchChange).not.toHaveBeenCalled();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("alert")).toHaveTextContent("优先权日期起始值不能晚于结束值");
  expect(dates.getByLabelText("起")).toHaveValue("2026-03-01");
});

it("rejects a mismatched patent detail identity rather than showing another family", async () => {
  act(() => setLocale("en"));
  vi.mocked(loadPatentFamilyDetail).mockResolvedValue({ ...patentResult.items[0], id: "another-patent" });
  renderPatent({ selectedPatentId: "patent-1" });
  expect(await screen.findByRole("alert")).toHaveTextContent("Patent detail does not match the requested identifier");
  expect(screen.queryByRole("heading", { name: patentResult.items[0].title })).not.toBeInTheDocument();
});

it("hides cached patent facts and facet counts after a current permission denial", async () => {
  act(() => setLocale("en"));
  const { queryClient } = renderPatent();
  await screen.findByRole("table", { name: "Patent family results" });
  vi.mocked(searchPatentFamilies).mockRejectedValue(new ApiError("Permission changed", 403, null));
  await act(() => queryClient.invalidateQueries({ queryKey: ["intelligence", "patents"] }));
  expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to these results");
  expect(screen.queryByRole("table", { name: "Patent family results" })).not.toBeInTheDocument();
  expect(screen.queryByText("Victor Therapeutics (101)")).not.toBeInTheDocument();
});

it("hides cached patent dossier metrics and source publications after a real transport permission denial", async () => {
  act(() => setLocale("en"));
  const { queryClient } = renderPatent({ selectedPatentId: "patent-1" });
  await screen.findByRole("table", { name: "Publications" });
  vi.mocked(loadPatentFamilyDetail).mockRejectedValue(new ApiError("RAW_DETAIL_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: ["intelligence", "patents", "detail", "patent-1"] }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_DETAIL_DENIAL");
  expect(screen.queryByRole("heading", { name: patentResult.items[0].title })).not.toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Publications" })).not.toBeInTheDocument();
});

it("does not transform inherited or unknown patent status codes", async () => {
  act(() => setLocale("en"));
  vi.mocked(searchPatentFamilies).mockResolvedValue({
    ...patentResult,
    items: [{ ...patentResult.items[0], legal_status: "constructor" }],
    facets: { applicant: {}, legal_status: { constructor: 1, custom_status: 2 } },
  });
  renderPatent();
  const table = await screen.findByRole("table", { name: "Patent family results" });
  expect(table).toHaveTextContent("constructor");
  expect(screen.getByRole("option", { name: "custom_status (2)" })).toBeInTheDocument();
});

it("retains a single pending patent save and translates its partial-success framing after switching", async () => {
  act(() => setLocale("en"));
  let finish: (outcome: SavedSearchCreationOutcome) => void = () => {
    throw new Error("Pending save not initialized");
  };
  vi.mocked(savePatentSearch).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  renderPatent({ initialQuery: "EGFR" });
  await screen.findByRole("table", { name: "Patent family results" });
  fireEvent.click(screen.getByRole("button", { name: "Save / subscribe" }));
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "原始研究名称" } });
  fireEvent.click(screen.getByRole("button", { name: "Save search" }));
  await waitFor(() => expect(savePatentSearch).toHaveBeenCalledTimes(1));
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("名称")).toHaveValue("原始研究名称");
  expect(screen.getByLabelText("名称")).toBeDisabled();
  await act(async () => finish({ kind: "monitor_failed", reason: "原始失败 <registry>" }));
  expect(await screen.findByText("检索已保存，但监控未启用：原始失败 <registry>")).toBeVisible();
  act(() => setLocale("en"));
  expect(screen.getByText("Search saved, but monitoring could not be enabled: 原始失败 <registry>")).toBeVisible();
  expect(savePatentSearch).toHaveBeenCalledTimes(1);
});

it("renders every source publication in the patent dossier without truncating applicant names", async () => {
  act(() => setLocale("en"));
  vi.mocked(loadPatentFamilyDetail).mockResolvedValue({
    ...patentResult.items[0],
    applicants: Array.from({ length: 10 }, (_, index) => `原始申请人 ${index}`),
    publications: [
      {
        publication_number: "WO2022123456A1",
        application_number: "PCT/原始申请号",
        jurisdiction: "WO",
        publication_date: "2022-08-04",
        grant_date: null,
      },
      { publication_number: "US-原始公开编号" },
    ],
  });
  renderPatent({ selectedPatentId: "patent-1" });
  const publications = await screen.findByRole("table", { name: "Publications" });
  expect(publications).toHaveTextContent("PCT/原始申请号");
  expect(publications).toHaveTextContent("US-原始公开编号");
  expect(screen.getByText(/原始申请人 9/)).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "公开文本" })).toHaveTextContent("US-原始公开编号");
  expect(loadPatentFamilyDetail).toHaveBeenCalledTimes(1);
});

it("localizes patent landscape captions without changing source applicants or drill-down keys", async () => {
  act(() => setLocale("en"));
  const onSearchChange = vi.fn();
  renderPatent({ displayMode: "landscape", analysisView: "table", onSearchChange });
  const status = await screen.findByRole("table", { name: "Legal status statistics" });
  expect(status).toHaveTextContent("Active");
  expect(screen.getByRole("table", { name: "Leading applicants statistics" })).toHaveTextContent("Victor Therapeutics");
  fireEvent.click(within(status).getByRole("button", { name: "Filter" }));
  expect(onSearchChange).toHaveBeenCalledWith(expect.objectContaining({ legalStatus: "ACTIVE" }), 0);
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "法律状态统计表" })).toHaveTextContent("有效");
  expect(searchPatentFamilies).toHaveBeenCalledTimes(1);
});
vi.mock("../lib/contracts/intelligence", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/intelligence")>();
  return { ...actual, getEntity: vi.fn(), lookupEntities: vi.fn() };
});

beforeEach(() => {
  vi.mocked(searchPatentFamilies).mockResolvedValue(patentResult);
  vi.mocked(loadPatentFamilyDetail).mockResolvedValue(patentResult.items[0]);
  vi.mocked(savePatentSearch).mockResolvedValue({ kind: "saved", monitoring: true });
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
    applied_filters: [{ field: "query", operator: "contains", value: "missing" }],
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

  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
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
