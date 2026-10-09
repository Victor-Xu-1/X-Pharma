import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { PipelineSaveOutcome } from "../lib/contracts/pipeline";
import { emptyPipelineSearchFilters, savePipelineSearch, searchPipelines } from "../lib/contracts/pipeline";
import type { PipelineSearchResult } from "../lib/generated";
import { initializeLocale, setLocale } from "../lib/i18n";
import { PipelineView } from "../views/PipelineView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/pipeline", async (original) => ({
  ...(await original<typeof import("../lib/contracts/pipeline")>()),
  searchPipelines: vi.fn(),
  savePipelineSearch: vi.fn(),
}));

const response: PipelineSearchResult = {
  items: [
    {
      id: "program-1",
      drug_entity_id: "drug-1",
      drug_name: "原始药物 EGFR",
      target_entity_id: "target-1",
      target_name: "EGFR",
      disease_entity_id: null,
      disease_name: null,
      organization_entity_id: null,
      organization_name: null,
      modality: "small molecule",
      mechanism_of_action: "原始机制 <EGFR>",
      phase: "phase_2",
      geography: "原始地区",
      status_detail: "原始状态",
      status_date: null,
      source_document_id: null,
      program_status: "active",
      clinical_trial_count: 0,
      deal_count: 0,
      development_rights_regions: [],
      commercialization_rights_regions: [],
      program_tags: ["next_generation", "未知标签"],
    },
  ],
  total: 1,
  offset: 0,
  limit: 20,
  as_of: "2026-10-09T01:00:00Z",
  query_schema_version: "pharma.pipeline.search.v13",
  sort_by: "status_date",
  sort_direction: "desc",
  applied_filters: [{ field: "q", operator: "contains", value: "EGFR" }],
  warnings: [],
  facets: { modality: { "small molecule": 1 }, deal_currency: { USD: 1 } },
  landscape: {
    total_programs: 1,
    distinct_drugs: 1,
    distinct_targets: 1,
    distinct_diseases: 0,
    distinct_organizations: 0,
    limit: 8,
    stage_scope: "overall",
    target_aggregation: "all",
    targets: [
      { key: "target-1", entity_id: "target-1", label: "EGFR 原名", count: 1, share: 1, phase_counts: { phase_2: 1 } },
    ],
  },
};
const props = {
  initialFilters: { ...emptyPipelineSearchFilters(), query: "EGFR" },
  displayMode: "list" as const,
  resultGrain: "program" as const,
  analysisDimension: "targets" as const,
  analysisView: "table" as const,
  analysisLimit: 8 as const,
  analysisStageScope: "overall" as const,
  targetAggregation: "all" as const,
  onSearchChange: vi.fn(),
  onDisplayModeChange: vi.fn(),
  onResultGrainChange: vi.fn(),
  onAnalysisChange: vi.fn(),
  onOpenDrug: vi.fn(),
  onOpenEntity: vi.fn(),
  onOpenTrialsForDrug: vi.fn(),
  onOpenDealsForDrug: vi.fn(),
};

beforeEach(() => {
  setLocale("en");
  vi.mocked(searchPipelines).mockResolvedValue(response);
  vi.mocked(savePipelineSearch).mockResolvedValue({ kind: "saved", monitoring: true });
});

it("opens a fresh pipeline interface in English, including filters, table captions and empty field states", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockReturnValue(null);
  initializeLocale();
  renderWithQueryClient(<PipelineView {...props} />);
  const table = await screen.findByRole("table", { name: "Drug and development pipeline results" });
  expect(screen.getByRole("form", { name: "Drug and pipeline filters" })).toBeInTheDocument();
  expect(screen.getByLabelText("Keyword")).toHaveValue("EGFR");
  expect(within(table).getByRole("columnheader", { name: "Drug" })).toBeInTheDocument();
  expect(table).toHaveTextContent("Small molecule");
  expect(table).toHaveTextContent("Next generation");
  expect(table).toHaveTextContent("0 trials");
  expect(table).toHaveTextContent("0 deals");
  expect(table).toHaveTextContent("Undisclosed");
  for (const raw of ["原始药物 EGFR", "原始机制 <EGFR>", "原始地区", "原始状态", "未知标签"]) {
    expect(table).toHaveTextContent(raw);
  }
  expect(table).not.toHaveTextContent("小分子");
});

it("retains unsubmitted drafts, selected rows, expanded controls, URL, cache and ordering across switching", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=pipeline&q=EGFR&sort=status_date%3Adesc");
  const originalUrl = window.location.href;
  const { queryClient } = renderWithQueryClient(<PipelineView {...props} />);
  await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "未提交草稿 EGFR" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Select Compare 原始药物 EGFR" }));
  const summary = screen.getByText("Clinical results and deal signals");
  const disclosure = summary.closest("details");
  if (!disclosure) throw new Error("Signal disclosure missing");
  disclosure.open = true;
  fireEvent.change(screen.getByLabelText("Minimum total potential amount"), { target: { value: "0" } });
  const cached = queryClient
    .getQueryCache()
    .getAll()
    .map((query) => query.state.data);
  act(() => setLocale("zh-CN"));
  expect(screen.getByLabelText("关键词")).toHaveValue("未提交草稿 EGFR");
  expect(screen.getByLabelText("潜在总额下限")).toHaveValue(0);
  expect(screen.getByRole("checkbox", { name: "取消选择对比 原始药物 EGFR" })).toBeChecked();
  expect(disclosure.open).toBe(true);
  expect(
    within(screen.getByRole("table", { name: "药物与研发管线结果" })).getByRole("columnheader", { name: /状态日期/ }),
  ).toHaveAttribute("aria-sort", "descending");
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Keyword")).toHaveValue("未提交草稿 EGFR");
  expect(window.location.href).toBe(originalUrl);
  expect(
    queryClient
      .getQueryCache()
      .getAll()
      .map((query) => query.state.data),
  ).toEqual(cached);
  expect(searchPipelines).toHaveBeenCalledTimes(1);
  expect(savePipelineSearch).not.toHaveBeenCalled();
  expect(props.onSearchChange).not.toHaveBeenCalled();
});

it("translates validation already on screen without querying or changing its zero-valued draft", async () => {
  renderWithQueryClient(<PipelineView {...props} />);
  await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.change(screen.getByLabelText("Minimum total potential amount"), { target: { value: "0" } });
  fireEvent.submit(screen.getByRole("form", { name: "Drug and pipeline filters" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Choose a currency to search by deal amount");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("alert")).toHaveTextContent("按交易金额查询时必须选择币种");
  expect(screen.getByLabelText("潜在总额下限")).toHaveValue(0);
  expect(props.onSearchChange).not.toHaveBeenCalled();
});

it("preserves the saved-query draft and translates completed feedback without replaying the write", async () => {
  renderWithQueryClient(<PipelineView {...props} />);
  await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.click(screen.getByRole("button", { name: "Save / monitor" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "研究员原名" } });
  act(() => setLocale("zh-CN"));
  expect(within(dialog).getByLabelText("名称")).toHaveValue("研究员原名");
  fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByRole("status")).toHaveTextContent("管线检索已保存并启用监控");
  act(() => setLocale("en"));
  expect(screen.getByText("Pipeline search saved and monitoring enabled")).toBeInTheDocument();
  expect(savePipelineSearch).toHaveBeenCalledTimes(1);
  expect(searchPipelines).toHaveBeenCalledTimes(1);
});

it("translates the bounded landscape controls, stages and tables without changing raw bucket identity or totals", async () => {
  renderWithQueryClient(<PipelineView {...props} displayMode="landscape" />);
  const table = await screen.findByRole("table", { name: "Targets statistics" });
  expect(table).toHaveTextContent("EGFR 原名");
  expect(table).toHaveTextContent("Phase II 1");
  expect(screen.getByLabelText("Analysis dimension")).toHaveValue("targets");
  expect(screen.getByLabelText("Target aggregation basis")).toHaveValue("all");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "靶点统计表" })).toHaveTextContent("II 期 1");
  expect(screen.getByLabelText("分析维度")).toHaveValue("targets");
  fireEvent.click(within(table).getByRole("button", { name: "筛选" }));
  expect(props.onSearchChange).toHaveBeenCalledWith({ ...props.initialFilters, targetEntityId: "target-1", offset: 0 });
  expect(searchPipelines).toHaveBeenCalledTimes(1);
});

it("keeps one pending query while translating its loading state and literal error recovery", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(searchPipelines).mockImplementationOnce(
    () =>
      new Promise<PipelineSearchResult>((_resolve, rejectPromise) => {
        reject = rejectPromise;
      }),
  );
  renderWithQueryClient(<PipelineView {...props} />);
  expect(screen.getByText("Searching development pipelines")).toBeInTheDocument();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("正在查询研发管线")).toBeInTheDocument();
  await act(async () => reject(new Error("原始失败 <EGFR>")));
  expect(await screen.findByRole("alert")).toHaveTextContent("原始失败 <EGFR>");
  act(() => setLocale("en"));
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("原始失败 <EGFR>");
  expect(searchPipelines).toHaveBeenCalledTimes(1);
});

it("uses a natural refresh caption in both languages while retaining the previous result and one request", async () => {
  let release!: (value: PipelineSearchResult) => void;
  vi.mocked(searchPipelines)
    .mockResolvedValueOnce(response)
    .mockImplementationOnce(
      () =>
        new Promise<PipelineSearchResult>((resolve) => {
          release = resolve;
        }),
    );
  renderWithQueryClient(<PipelineView {...props} />);
  const table = await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.click(screen.getByRole("button", { name: "Refresh current results" }));
  expect(await screen.findByText("Refreshing development pipelines")).toBeInTheDocument();
  expect(table).toHaveTextContent("原始药物 EGFR");
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("正在刷新研发管线")).toBeInTheDocument();
  await act(async () => release(response));
  expect(searchPipelines).toHaveBeenCalledTimes(2);
});

it("can clear an unsubmitted draft even when the applied query has no filters", async () => {
  renderWithQueryClient(<PipelineView {...props} initialFilters={emptyPipelineSearchFilters()} />);
  await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "未提交草稿" } });
  const clear = screen.getByRole("button", { name: "Clear" });
  expect(clear).toBeEnabled();
  fireEvent.click(clear);
  expect(screen.getByLabelText("Keyword")).toHaveValue("");
  expect(props.onSearchChange).toHaveBeenCalledExactlyOnceWith(emptyPipelineSearchFilters());
});

it("retains the disabled save draft through a pending language change and a recoverable literal rejection", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(savePipelineSearch).mockImplementationOnce(
    () =>
      new Promise<PipelineSaveOutcome>((_resolve, rejectPromise) => {
        reject = rejectPromise;
      }),
  );
  renderWithQueryClient(<PipelineView {...props} />);
  await screen.findByRole("table", { name: "Drug and development pipeline results" });
  fireEvent.click(screen.getByRole("button", { name: "Save / monitor" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "原始保存草稿" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save search" }));
  await waitFor(() => expect(dialog).toHaveAttribute("aria-busy", "true"));
  act(() => setLocale("zh-CN"));
  expect(within(dialog).getByLabelText("名称")).toHaveValue("原始保存草稿");
  expect(within(dialog).getByRole("button", { name: "保存中" })).toBeDisabled();
  await act(async () => reject(new Error("原始服务端保存失败 <EGFR>")));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("原始服务端保存失败 <EGFR>");
  act(() => setLocale("en"));
  expect(within(dialog).getByLabelText("Name")).toHaveValue("原始保存草稿");
  expect(within(dialog).getByRole("button", { name: "Save search" })).toBeEnabled();
  expect(savePipelineSearch).toHaveBeenCalledTimes(1);
});
