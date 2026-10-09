import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { loadTrialDetail, saveClinicalTrialSearch, searchTrials } from "../lib/contracts/trials";
import { setLocale } from "../lib/i18n";
import { TrialsView } from "../views/TrialsView";
import { trialDetail, trialId, trialResult } from "./fixtures/clinicalTrial";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/trials", async (original) => ({
  ...(await original<typeof import("../lib/contracts/trials")>()),
  searchTrials: vi.fn(),
  loadTrialDetail: vi.fn(),
  saveClinicalTrialSearch: vi.fn(),
}));
const props: ComponentProps<typeof TrialsView> = {
  displayMode: "list",
  analysisView: "chart",
  initialQuery: "EGFR",
  initialRegistry: "",
  initialStatus: "",
  initialPhase: "",
  initialStudyType: "",
  initialAcronym: "",
  initialInitiationType: "",
  initialTherapyLine: "",
  initialHasResults: "",
  initialResultEvaluation: "",
  initialResultsPostedFrom: "",
  initialResultsPostedTo: "",
  initialInvestigationalDrug: "",
  initialCombinationDrug: "",
  initialInvestigationalTarget: "",
  initialCombinationTarget: "",
  initialInvestigationalDrugEntityIds: [],
  initialCombinationDrugEntityIds: [],
  initialInvestigationalTargetEntityIds: [],
  initialCombinationTargetEntityIds: [],
  initialLinkedDrugModalities: [],
  initialLinkedDrugInnovationTypes: [],
  initialLinkedDrugCategories: [],
  initialLinkedDrugProgramTags: [],
  initialLinkedDrugGlobalPhase: "",
  initialLinkedDrugOrganizationCountryRegion: "",
  initialRoleEntityId: "",
  initialRoleEntityIds: [],
  initialRoleEntityRole: "",
  initialHasKeyResult: "",
  initialPublicationId: "",
  initialConference: "",
  initialDisclosedFrom: "",
  initialDisclosedTo: "",
  initialSortBy: "last_update_posted",
  initialSortDirection: "desc",
  initialOffset: 0,
  selectedTrialId: null,
  activeSection: "overview",
  onSearchChange: vi.fn(),
  onTrialChange: vi.fn(),
  onSectionChange: vi.fn(),
  onOpenEntity: vi.fn(),
  onDisplayModeChange: vi.fn(),
  onAnalysisViewChange: vi.fn(),
};
beforeEach(() => {
  setLocale("zh-CN");
  vi.mocked(searchTrials).mockResolvedValue(trialResult);
  vi.mocked(loadTrialDetail).mockResolvedValue(trialDetail);
  vi.mocked(saveClinicalTrialSearch).mockResolvedValue({ kind: "saved", monitoring: true });
});

it("renders all clinical query/table captions in English while preserving raw study identity and controlled values", async () => {
  setLocale("en");
  renderWithQueryClient(<TrialsView {...props} />);
  const table = await screen.findByRole("table", { name: "Clinical trial results" });
  expect(screen.getByRole("form", { name: "Clinical trial filters" })).toBeInTheDocument();
  expect(screen.getByLabelText("Keyword")).toHaveValue("EGFR");
  expect(table).toHaveTextContent(trialDetail.registry_id);
  expect(table).toHaveTextContent(trialDetail.official_title);
  expect(table).toHaveTextContent("Recruiting");
  expect(table).toHaveTextContent("Phase II");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "临床试验结果" })).toHaveTextContent("招募中");
  expect(searchTrials).toHaveBeenCalledTimes(1);
});

it("keeps all unsubmitted fields when equivalent applied arrays are recreated by the parent", async () => {
  const view = renderWithQueryClient(<TrialsView {...props} />);
  await screen.findByRole("table", { name: "临床试验结果" });
  fireEvent.change(screen.getByLabelText("关键词"), { target: { value: "未提交原文" } });
  fireEvent.change(screen.getByLabelText("会议"), { target: { value: "原始会议" } });
  view.rerender(
    <TrialsView
      {...props}
      initialInvestigationalDrugEntityIds={[]}
      initialLinkedDrugModalities={[]}
      initialRoleEntityIds={[]}
    />,
  );
  expect(screen.getByLabelText("关键词")).toHaveValue("未提交原文");
  expect(screen.getByLabelText("会议")).toHaveValue("原始会议");
  expect(searchTrials).toHaveBeenCalledTimes(1);
});

it("allows clearing an unsubmitted draft without changing the chosen view or sort", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <TrialsView
      {...props}
      initialQuery=""
      displayMode="landscape"
      analysisView="table"
      initialSortBy="registry_id"
      initialSortDirection="asc"
      onSearchChange={onSearchChange}
    />,
  );
  await screen.findByRole("button", { name: "保存/订阅" });
  expect(screen.getByRole("button", { name: "清除" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("关键词"), { target: { value: "未提交原文" } });
  expect(screen.getByRole("button", { name: "清除" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  expect(screen.getByLabelText("关键词")).toHaveValue("");
  expect(onSearchChange).toHaveBeenCalledWith(
    expect.objectContaining({
      query: "",
      displayMode: "landscape",
      analysisView: "table",
      sortBy: "registry_id",
      sortDirection: "asc",
      offset: 0,
    }),
  );
});

it("uses the recorded month/year precision rather than displaying invented calendar days", async () => {
  vi.mocked(loadTrialDetail).mockResolvedValue({
    ...trialDetail,
    start_date: "2025-01-01T00:00:00Z",
    start_date_precision: "year",
    completion_date: "2026-07-01T00:00:00Z",
    completion_date_precision: "month",
  });
  renderWithQueryClient(<TrialsView {...props} selectedTrialId={trialId} />);
  await screen.findByRole("heading", { name: trialDetail.official_title });
  expect(screen.getByText("2025年")).toBeInTheDocument();
  expect(screen.getByText("2026年07月")).toBeInTheDocument();
  expect(screen.queryByText("2026/07/01")).not.toBeInTheDocument();
});

it("does not invent a 95 percent confidence level, hide analysis notes, or drop a reported partial zero bound", async () => {
  const outcome = trialDetail.outcomes[0];
  vi.mocked(loadTrialDetail).mockResolvedValue({
    ...trialDetail,
    outcomes: [
      {
        ...outcome,
        results: [
          {
            group_label: "原始 cohort",
            value: "0",
            participants: 0,
            lower_limit: 0,
            upper_limit: null,
            dispersion: "原始 dispersion",
          },
        ],
        statistical_analyses: [
          {
            method: "原始方法",
            parameter_type: "原始参数",
            parameter_value: 0,
            p_value: "0",
            confidence_interval_percent: null,
            lower_limit: 0,
            upper_limit: 1,
            notes: "原始分析说明",
          },
        ],
      },
    ],
  });
  renderWithQueryClient(<TrialsView {...props} selectedTrialId={trialId} activeSection="outcomes" />);
  await screen.findByRole("heading", { name: trialDetail.official_title });
  expect(screen.queryByText(/95% CI/)).not.toBeInTheDocument();
  expect(screen.getByText("原始分析说明")).toBeInTheDocument();
  expect(screen.getByText("原始参数")).toBeInTheDocument();
  const row = screen.getByRole("row", { name: /原始 cohort/ });
  expect(within(row).getByText(/下限.*0/)).toBeInTheDocument();
  expect(row).toHaveTextContent("原始 dispersion");
});

it("preserves both model and masking notes instead of presenting only the first available description", async () => {
  vi.mocked(loadTrialDetail).mockResolvedValue({
    ...trialDetail,
    study_design: {
      ...trialDetail.study_design,
      intervention_model_description: "原始模型说明",
      masking_description: "原始盲法说明",
    },
  });
  renderWithQueryClient(<TrialsView {...props} selectedTrialId={trialId} activeSection="design" />);
  await screen.findByRole("heading", { name: trialDetail.official_title });
  expect(screen.getByText("原始模型说明")).toBeInTheDocument();
  expect(screen.getByText("原始盲法说明")).toBeInTheDocument();
});

it("keeps the header focused on six primary metrics while retaining secondary registration fields in overview", async () => {
  setLocale("en");
  renderWithQueryClient(<TrialsView {...props} selectedTrialId={trialId} />);
  await screen.findByRole("heading", { name: trialDetail.official_title });
  const metrics = document.querySelector(".trial-professional-metrics");
  expect(metrics?.children).toHaveLength(6);
  expect(screen.getByText(trialDetail.acronym ?? "")).toBeInTheDocument();
  expect(screen.getByText("IST (sponsor-initiated)")).toBeInTheDocument();
  expect(screen.getByText("First-line therapy")).toBeInTheDocument();
});

it("retains selection, draft fields and linked-filter disclosure on a language switch without repeating the query", async () => {
  const { queryClient } = renderWithQueryClient(<TrialsView {...props} />);
  await screen.findByRole("table", { name: "临床试验结果" });
  const originalCache = queryClient
    .getQueryCache()
    .getAll()
    .map((query) => [query.queryKey, query.state.data]);
  fireEvent.click(screen.getByRole("checkbox", { name: `选择对比 ${trialDetail.registry_id}` }));
  fireEvent.change(screen.getByLabelText("关键词"), { target: { value: "原始草稿 EGFR" } });
  const disclosure = screen.getByText("关联药物属性").closest("details");
  if (!disclosure) throw new Error("Missing linked filter disclosure");
  const summary = disclosure.querySelector("summary");
  if (!summary) throw new Error("Missing linked filter summary");
  fireEvent.click(summary);
  await waitFor(() => expect(disclosure).toHaveAttribute("open"));
  act(() => setLocale("en"));
  expect(screen.getByRole("checkbox", { name: `Deselect Compare ${trialDetail.registry_id}` })).toBeChecked();
  expect(screen.getByLabelText("Keyword")).toHaveValue("原始草稿 EGFR");
  expect(screen.getByText("Linked drug attributes").closest("details")).toHaveAttribute("open");
  expect(searchTrials).toHaveBeenCalledTimes(1);
  expect(
    queryClient
      .getQueryCache()
      .getAll()
      .map((query) => [query.queryKey, query.state.data]),
  ).toEqual(originalCache);
});

it("does not submit twice or lose modal intent when language changes during a pending save", async () => {
  let finish: ((result: Awaited<ReturnType<typeof saveClinicalTrialSearch>>) => void) | undefined;
  vi.mocked(saveClinicalTrialSearch).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  renderWithQueryClient(<TrialsView {...props} />);
  fireEvent.click(await screen.findByRole("button", { name: "保存/订阅" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "原始研究名称" } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));
  await waitFor(() => expect(saveClinicalTrialSearch).toHaveBeenCalledTimes(1));
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Name")).toHaveValue("原始研究名称");
  expect(screen.getByLabelText("Share this search within your organization")).toBeChecked();
  expect(screen.getByRole("button", { name: "Saving" })).toBeDisabled();
  expect(screen.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
  await act(async () => finish?.({ kind: "monitor_failed", reason: "原始 provider reason <EGFR>" }));
  await screen.findByText("Search saved, but monitoring was not enabled: 原始 provider reason <EGFR>");
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("检索已保存，但监控未启用：原始 provider reason <EGFR>")).toBeInTheDocument();
  expect(saveClinicalTrialSearch).toHaveBeenCalledTimes(1);
  expect(saveClinicalTrialSearch).toHaveBeenCalledWith(
    expect.objectContaining({ name: "原始研究名称", shared: true, monitor: true }),
    expect.anything(),
  );
});

it.each([401, 403])("hides cached search records after a confirmed %s access denial", async (status) => {
  setLocale("en");
  const { queryClient } = renderWithQueryClient(<TrialsView {...props} />);
  await screen.findByRole("table", { name: "Clinical trial results" });
  vi.mocked(searchTrials).mockRejectedValue(new ApiError("Raw denial", status, null));
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: ["intelligence", "trials"] });
  });
  await waitFor(() => expect(screen.queryByRole("table", { name: "Clinical trial results" })).not.toBeInTheDocument());
  expect(screen.queryByText(trialDetail.official_title)).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Applied query conditions" })).not.toBeInTheDocument();
});

it.each([401, 403])("hides cached dossier content and identity after a confirmed %s access denial", async (status) => {
  setLocale("en");
  const { queryClient } = renderWithQueryClient(<TrialsView {...props} selectedTrialId={trialId} />);
  await screen.findByRole("heading", { name: trialDetail.official_title });
  vi.mocked(loadTrialDetail).mockRejectedValue(new ApiError("Raw denial", status, null));
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: ["intelligence", "trials", "detail", trialId] });
  });
  await waitFor(() =>
    expect(screen.queryByRole("heading", { name: trialDetail.official_title })).not.toBeInTheDocument(),
  );
  expect(screen.queryByText(trialDetail.registry_id)).not.toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Design and eligibility" })).not.toBeInTheDocument();
  expect(screen.getByText("Raw denial")).toBeInTheDocument();
});
