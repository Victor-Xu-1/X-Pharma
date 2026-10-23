import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  emptyRegulatorySearchFilters,
  loadRegulatoryEventDetail,
  saveRegulatorySearch,
  searchRegulatoryEvents,
} from "../lib/contracts/regulatory";
import { RegulatoryView } from "../views/RegulatoryView";
import { eventId, regulatoryEvent, regulatoryResult } from "./fixtures/regulatoryResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/regulatory", async () => {
  const actual = await vi.importActual<typeof import("../lib/contracts/regulatory")>("../lib/contracts/regulatory");
  return {
    ...actual,
    regulatoryKeys: {
      search: (filters: Record<string, string>, offset: number) => ["regulatory", { ...filters, offset }],
      detail: (eventId: string) => ["regulatory", "detail", eventId],
    },
    searchRegulatoryEvents: vi.fn(),
    loadRegulatoryEventDetail: vi.fn(),
    saveRegulatorySearch: vi.fn(),
  };
});

function renderView(overrides: Partial<ComponentProps<typeof RegulatoryView>> = {}) {
  return renderWithQueryClient(
    <RegulatoryView
      initialFilters={{ ...emptyRegulatorySearchFilters, query: "VX-101" }}
      initialOffset={0}
      selectedEventId={null}
      comparedEventIds={[]}
      onSearchChange={vi.fn()}
      onEventChange={vi.fn()}
      onCompareChange={vi.fn()}
      onOpenEntity={vi.fn()}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  vi.mocked(searchRegulatoryEvents).mockResolvedValue(regulatoryResult);
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue(regulatoryEvent);
  vi.mocked(saveRegulatorySearch).mockResolvedValue({ kind: "saved", monitoring: true });
});

it("renders governed regulatory intelligence and opens a stable event detail", async () => {
  const onEventChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderView({ onEventChange, onOpenEntity, onOpenDrug, onOpenTarget, onOpenDisease, onOpenOrganization });

  expect(await screen.findByRole("table", { name: "监管事件结果" })).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|数据授权/);
  expect(searchRegulatoryEvents).toHaveBeenCalledWith(
    { ...emptyRegulatorySearchFilters, query: "VX-101" },
    0,
    expect.any(AbortSignal),
  );
  expect(screen.getByText("突破性疗法")).toBeInTheDocument();
  const resultTable = screen.getByRole("table", { name: "监管事件结果" });
  fireEvent.click(within(resultTable).getByRole("button", { name: /VX-101NDA 219999/ }));
  expect(onOpenDrug).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440001");
  fireEvent.click(within(resultTable).getByRole("button", { name: "EGFR-positive NSCLC" }));
  expect(onOpenDisease).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /VX-101 approved/ }));
  expect(onEventChange).toHaveBeenCalledWith(eventId);

  renderView({
    selectedEventId: eventId,
    onEventChange,
    onOpenEntity,
    onOpenDrug,
    onOpenTarget,
    onOpenDisease,
    onOpenOrganization,
  });
  expect(await screen.findByRole("dialog", { name: "VX-101 approved for EGFR-positive NSCLC" })).toBeInTheDocument();
  expect(loadRegulatoryEventDetail).toHaveBeenCalledWith(eventId, expect.any(AbortSignal));
  expect(screen.getByText("Monitor pulmonary symptoms")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "打开 Acme Pharma 档案" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440003");
  fireEvent.click(screen.getByTitle("关闭"));
  expect(onEventChange).toHaveBeenCalledWith(null);
});

it("submits advanced label and safety filters and validates date ranges", async () => {
  const onSearchChange = vi.fn();
  renderView({ onSearchChange });
  await screen.findByRole("table", { name: "监管事件结果" });

  fireEvent.change(screen.getByLabelText("监管机构"), { target: { value: "FDA" } });
  fireEvent.change(screen.getByLabelText("辖区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("事件类型"), { target: { value: "approval" } });
  fireEvent.change(screen.getByLabelText("认定资格"), { target: { value: "breakthrough_therapy" } });
  fireEvent.click(screen.getByText("更多监管与安全条件"));
  fireEvent.change(screen.getByLabelText("标签变更"), { target: { value: "initial_label" } });
  fireEvent.change(screen.getByLabelText("黑框警告"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("安全信号"), { target: { value: "adverse_event" } });
  fireEvent.change(screen.getByLabelText("严重程度"), { target: { value: "serious" } });
  fireEvent.change(screen.getByLabelText("信号状态"), { target: { value: "confirmed" } });
  const decisionDates = screen.getByRole("group", { name: "决定日期" }).querySelectorAll("input");
  fireEvent.change(decisionDates[0], { target: { value: "2026-03-01" } });
  fireEvent.change(decisionDates[1], { target: { value: "2026-02-01" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(screen.getByRole("alert")).toHaveTextContent("决定日期起始值不能晚于结束值");
  expect(onSearchChange).not.toHaveBeenCalled();

  fireEvent.change(decisionDates[0], { target: { value: "2026-01-01" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(onSearchChange).toHaveBeenCalledWith(
    expect.objectContaining({
      query: "VX-101",
      agency: "FDA",
      jurisdiction: "US",
      eventType: "approval",
      designationType: "breakthrough_therapy",
      labelChangeType: "initial_label",
      boxedWarning: "true",
      safetySignalType: "adverse_event",
      safetySeverity: "serious",
      safetyStatus: "confirmed",
      decisionFrom: "2026-01-01",
      decisionTo: "2026-02-01",
    }),
    0,
  );
});

it("loads and removes selected events in the semantic comparison table", async () => {
  const onCompareChange = vi.fn();
  renderView({ comparedEventIds: [eventId], onCompareChange });

  expect(await screen.findByRole("table", { name: "监管事件对比" })).toBeInTheDocument();
  expect(screen.getByText("Interstitial lung disease / 严重")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: `移除 ${regulatoryEvent.title}` }));
  expect(onCompareChange).toHaveBeenCalledWith([]);
});

it("connects governed table row selection to the URL-owned comparison state", async () => {
  const onCompareChange = vi.fn();
  const firstRender = renderView({ onCompareChange });

  expect(await screen.findByRole("table", { name: "监管事件结果" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: `选择对比 ${regulatoryEvent.title}` }));
  expect(onCompareChange).toHaveBeenCalledWith([eventId]);
  firstRender.unmount();

  const limitIds = ["event-1", "event-2", "event-3", "event-4"];
  vi.mocked(loadRegulatoryEventDetail).mockImplementation(async (requestedEventId) => ({
    ...regulatoryEvent,
    id: requestedEventId,
    title: `Regulatory event ${requestedEventId}`,
  }));
  renderView({ comparedEventIds: limitIds, onCompareChange });
  expect(await screen.findByRole("checkbox", { name: `选择对比 ${regulatoryEvent.title}` })).toBeDisabled();
  expect(screen.queryByRole("checkbox", { name: "选择当前页" })).not.toBeInTheDocument();
});

it("renders the explicit regulatory empty state and clears active filters", async () => {
  vi.mocked(searchRegulatoryEvents).mockResolvedValue({
    ...regulatoryResult,
    items: [],
    applied_filters: [
      { field: "query", operator: "contains", value: "missing" },
      { field: "agency", operator: "eq", value: "FDA" },
    ],
    total: 0,
    facets: {},
    landscape: { total_events: 0, event_type: [], agency: [], decision_year: [] },
  });
  const onSearchChange = vi.fn();
  renderView({
    initialFilters: { ...emptyRegulatorySearchFilters, query: "missing", agency: "FDA" },
    onSearchChange,
  });

  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() => expect(onSearchChange).toHaveBeenCalledWith(emptyRegulatorySearchFilters, 0));
});

it("renders a recoverable regulatory query error", async () => {
  vi.mocked(searchRegulatoryEvents).mockRejectedValue(new Error("Regulatory source unavailable"));
  renderView({ initialFilters: emptyRegulatorySearchFilters });
  expect(await screen.findByText("Regulatory source unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("requests a full-result regulatory sort from a sortable header", async () => {
  const onSearchChange = vi.fn();
  renderView({ onSearchChange });
  const table = await screen.findByRole("table");
  const titleHeader = within(table).getAllByRole("columnheader")[1];
  fireEvent.click(within(titleHeader).getByRole("button"));

  expect(onSearchChange).toHaveBeenCalledWith(
    {
      ...emptyRegulatorySearchFilters,
      query: "VX-101",
      sortBy: "title",
      sortDirection: "asc",
      sort: [{ field: "title", direction: "asc" }],
    },
    0,
  );
});

it("saves and subscribes the authoritative applied regulatory query", async () => {
  const filters = {
    ...emptyRegulatorySearchFilters,
    query: "VX-101",
    agency: "FDA",
    boxedWarning: "false",
    sortBy: "source_updated_at" as const,
    sortDirection: "asc" as const,
  };
  renderView({ initialFilters: filters });
  await screen.findByRole("table", { name: "监管事件结果" });

  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  expect(screen.getByRole("dialog", { name: "保存当前监管检索" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "FDA safety watch" } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(saveRegulatorySearch).toHaveBeenCalledWith(
      {
        name: "FDA safety watch",
        filters,
        shared: true,
        monitor: true,
      },
      expect.anything(),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("监管检索已保存并启用监控");
});

it("does not save a regulatory search that only contains sorting defaults", async () => {
  renderView({ initialFilters: emptyRegulatorySearchFilters });
  await screen.findByRole("table", { name: "监管事件结果" });
  expect(screen.getByRole("button", { name: "保存/订阅" })).toBeDisabled();
});
