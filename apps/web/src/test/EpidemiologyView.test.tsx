import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import type { EpidemiologyFilters } from "../lib/contracts/epidemiology";
import { loadEpidemiologyTrend, saveEpidemiologySearch, searchEpidemiology } from "../lib/contracts/epidemiology";
import { EpidemiologyView } from "../views/EpidemiologyView";
import { emptyFilters, observation, searchResult } from "./fixtures/epidemiologyResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/epidemiology", async () => {
  const actual = await vi.importActual<typeof import("../lib/contracts/epidemiology")>("../lib/contracts/epidemiology");
  return {
    ...actual,
    epidemiologyKeys: {
      search: (filters: EpidemiologyFilters, offset: number) => ["epidemiology", "search", filters, offset],
      trend: (diseaseId: string, filters: EpidemiologyFilters) => ["epidemiology", "trend", diseaseId, filters],
    },
    searchEpidemiology: vi.fn(),
    loadEpidemiologyTrend: vi.fn(),
    saveEpidemiologySearch: vi.fn(),
  };
});

vi.mock("../components/RecordProvenanceDrawer", () => ({
  ProvenanceButton: ({ selection, onOpen }: { selection: unknown; onOpen: (value: unknown) => void }) => (
    <button type="button" aria-label="查看原始证据" onClick={() => onOpen(selection)}>
      证据
    </button>
  ),
  RecordProvenanceDrawer: ({ selection }: { selection: { label: string } }) => (
    <div role="dialog" aria-label="原始证据面板">
      {selection.label}
    </div>
  ),
}));

beforeEach(() => {
  vi.mocked(searchEpidemiology).mockResolvedValue(searchResult);
  vi.mocked(loadEpidemiologyTrend).mockResolvedValue({
    disease: observation.disease_entity,
    items: [
      {
        ...observation,
        id: "observation-0",
        value: 145000,
        period_start: "2024-01-01T00:00:00Z",
        period_end: "2024-12-31T00:00:00Z",
      },
      observation,
    ],
    total: 2,
    truncated: false,
    as_of: "2026-07-22T10:00:00Z",
    warnings: ["趋势仅比较相同口径。"],
  });
  vi.mocked(saveEpidemiologySearch).mockResolvedValue({ message: "流行病学检索已保存并启用监控" });
});

it("renders governed disease burden, opens entities, comparable trends and provenance", async () => {
  const onSearchChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  renderWithQueryClient(
    <EpidemiologyView
      initialFilters={{ ...emptyFilters, query: "NSCLC" }}
      initialOffset={0}
      onSearchChange={onSearchChange}
      onOpenEntity={onOpenEntity}
      onOpenDrug={onOpenDrug}
      onOpenTarget={onOpenTarget}
      onOpenDisease={onOpenDisease}
      onOpenOrganization={onOpenOrganization}
    />,
  );

  expect(await screen.findByRole("table", { name: "流行病学结果" })).toBeInTheDocument();
  expect(
    screen.getByText("按疾病、人群、地区、时间和统计口径查询患病、发病、死亡及患者规模数据。"),
  ).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|授权来源/);
  expect(searchEpidemiology).toHaveBeenCalledWith({ ...emptyFilters, query: "NSCLC" }, 0, expect.any(AbortSignal));
  fireEvent.click(screen.getByRole("button", { name: "EGFR-positive NSCLC" }));
  expect(onOpenDisease).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440001");
  fireEvent.click(screen.getByRole("button", { name: "WHO" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("button", { name: "查看 EGFR-positive NSCLC 同口径趋势" }));
  expect(await screen.findByRole("table", { name: "同口径趋势数据" })).toBeInTheDocument();
  await waitFor(() =>
    expect(loadEpidemiologyTrend).toHaveBeenCalledWith(
      "550e8400-e29b-41d4-a716-446655440001",
      "observation-1",
      expect.objectContaining({
        measure: "prevalence",
        geography: "China",
        unit: "patients",
        patientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
        populationScope: "adults",
        ageGroup: "18+",
        sex: "all",
      }),
      expect.any(AbortSignal),
    ),
  );
  expect(screen.getByText("145,000")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "查看原始证据" }));
  expect(screen.getByRole("dialog", { name: "原始证据面板" })).toHaveTextContent("EGFR-positive NSCLC 患病率");

  fireEvent.change(screen.getByLabelText("统计指标"), { target: { value: "prevalence" } });
  fireEvent.change(screen.getByLabelText("地区"), { target: { value: "China" } });
  fireEvent.change(screen.getByLabelText("标准患者人群"), {
    target: { value: "550e8400-e29b-41d4-a716-446655440003" },
  });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(onSearchChange).toHaveBeenCalledWith(
    expect.objectContaining({
      query: "NSCLC",
      measure: "prevalence",
      geography: "China",
      patientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
    }),
    0,
  );
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenCalledWith({ ...emptyFilters, query: "NSCLC" }, 100);
});

it("renders the explicit empty state and clears active filters", async () => {
  vi.mocked(searchEpidemiology).mockResolvedValue({
    ...searchResult,
    items: [],
    total: 0,
    facets: {},
    applied_filters: [
      { field: "query", operator: "contains", value: "missing" },
      { field: "geography", operator: "eq", value: "China" },
    ],
  });
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <EpidemiologyView
      initialFilters={{ ...emptyFilters, query: "missing", geography: "China" }}
      initialOffset={0}
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  expect(onSearchChange).toHaveBeenCalledWith(emptyFilters, 0);
});

it("renders a recoverable epidemiology query error", async () => {
  vi.mocked(searchEpidemiology).mockRejectedValue(new Error("Epidemiology source unavailable"));
  renderWithQueryClient(
    <EpidemiologyView
      initialFilters={emptyFilters}
      initialOffset={0}
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("Epidemiology source unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("requests a full-result epidemiology sort from a sortable header", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <EpidemiologyView
      initialFilters={{ ...emptyFilters, query: "NSCLC" }}
      initialOffset={0}
      onSearchChange={onSearchChange}
      onOpenEntity={vi.fn()}
    />,
  );
  const table = await screen.findByRole("table");
  const valueHeader = within(table).getAllByRole("columnheader")[1];
  fireEvent.click(within(valueHeader).getByRole("button"));

  expect(onSearchChange).toHaveBeenCalledWith(
    {
      ...emptyFilters,
      query: "NSCLC",
      sortBy: "value",
      sortDirection: "desc",
      sort: [{ field: "value", direction: "desc" }],
    },
    0,
  );
});

it("saves and subscribes the authoritative applied epidemiology query", async () => {
  const filters: EpidemiologyFilters = {
    ...emptyFilters,
    query: "NSCLC",
    diseaseEntityId: "550e8400-e29b-41d4-a716-446655440001",
    measure: "prevalence",
    geography: "China",
    patientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
    periodStartFrom: "2025-01-01",
    periodEndTo: "2025-12-31",
    sortBy: "value",
  };
  renderWithQueryClient(
    <EpidemiologyView initialFilters={filters} initialOffset={0} onSearchChange={vi.fn()} onOpenEntity={vi.fn()} />,
  );
  await screen.findByRole("table", { name: "流行病学结果" });

  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "China NSCLC burden" } });
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(saveEpidemiologySearch).toHaveBeenCalledWith(
      { name: "China NSCLC burden", filters, shared: false, monitor: true },
      expect.anything(),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("流行病学检索已保存并启用监控");
});

it("does not save an epidemiology query that only contains sorting defaults", async () => {
  renderWithQueryClient(
    <EpidemiologyView
      initialFilters={emptyFilters}
      initialOffset={0}
      onSearchChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "流行病学结果" });
  expect(screen.getByRole("button", { name: "保存/订阅" })).toBeDisabled();
});
