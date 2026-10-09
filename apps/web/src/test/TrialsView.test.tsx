import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { loadTrialDetail, saveClinicalTrialSearch, searchTrials } from "../lib/contracts/trials";
import { TrialsView } from "../views/TrialsView";
import { trialDetail, trialId, trialResult } from "./fixtures/clinicalTrial";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/trials", () => ({
  trialSortFields: [
    "last_update_posted",
    "registry_id",
    "has_results",
    "result_evaluation",
    "overall_status",
    "enrollment",
    "study_type",
    "acronym",
    "initiation_type",
  ],
  trialKeys: {
    search: (...args: unknown[]) => ["trials", args],
    detail: (trialId: string) => ["trials", "detail", trialId],
  },
  searchTrials: vi.fn(),
  loadTrialDetail: vi.fn(),
  saveClinicalTrialSearch: vi.fn(),
  hasTrialSearchFilter: (input: { query: string }) => Boolean(input.query),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(searchTrials).mockResolvedValue(trialResult);
  vi.mocked(loadTrialDetail).mockResolvedValue(trialDetail);
  vi.mocked(saveClinicalTrialSearch).mockResolvedValue({ kind: "saved", monitoring: true });
});

it("renders governed trial intelligence, filters it and opens linked records", async () => {
  const onSearchChange = vi.fn();
  const onTrialChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onDisplayModeChange = vi.fn();
  renderWithQueryClient(
    <TrialsView
      displayMode="list"
      initialQuery="EGFR"
      initialRegistry=""
      initialStatus=""
      initialPhase=""
      initialStudyType=""
      initialAcronym=""
      initialInitiationType=""
      initialTherapyLine=""
      initialHasResults=""
      initialResultEvaluation=""
      initialResultsPostedFrom=""
      initialResultsPostedTo=""
      initialInvestigationalDrug=""
      initialCombinationDrug=""
      initialInvestigationalTarget=""
      initialCombinationTarget=""
      initialInvestigationalDrugEntityIds={[]}
      initialCombinationDrugEntityIds={[]}
      initialInvestigationalTargetEntityIds={[]}
      initialCombinationTargetEntityIds={[]}
      initialLinkedDrugModalities={[]}
      initialLinkedDrugInnovationTypes={[]}
      initialLinkedDrugCategories={[]}
      initialLinkedDrugProgramTags={[]}
      initialLinkedDrugGlobalPhase=""
      initialLinkedDrugOrganizationCountryRegion=""
      initialRoleEntityId=""
      initialRoleEntityIds={[]}
      initialRoleEntityRole=""
      initialHasKeyResult=""
      initialPublicationId=""
      initialConference=""
      initialDisclosedFrom=""
      initialDisclosedTo=""
      initialSortBy="last_update_posted"
      initialSortDirection="desc"
      initialOffset={0}
      selectedTrialId={null}
      activeSection="overview"
      onSearchChange={onSearchChange}
      onTrialChange={onTrialChange}
      onSectionChange={vi.fn()}
      onOpenEntity={onOpenEntity}
      onOpenDrug={onOpenDrug}
      onOpenTarget={onOpenTarget}
      onDisplayModeChange={onDisplayModeChange}
      analysisView="chart"
      onAnalysisViewChange={vi.fn()}
    />,
  );

  expect(await screen.findByRole("table", { name: "临床试验结果" })).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|授权来源/);
  expect(screen.getByText(/全部结果按最近更新降序/)).toBeInTheDocument();
  expect(searchTrials).toHaveBeenCalledWith(
    "EGFR",
    ...Array(15).fill(""),
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    "",
    "",
    "",
    [],
    ...Array(6).fill(""),
    "last_update_posted",
    "desc",
    0,
    expect.any(AbortSignal),
    undefined,
  );
  expect(screen.getByText("NCT01234567")).toBeInTheDocument();
  expect(screen.getByText("招募中")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "可视化" }));
  expect(onDisplayModeChange).toHaveBeenCalledWith("landscape");
  expect(screen.getByRole("region", { name: "已应用查询条件" })).toHaveTextContent("关键词EGFR");
  fireEvent.click(screen.getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  fireEvent.click(screen.getByRole("button", { name: "试验药物: VX-101" }));
  expect(onOpenDrug).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440003");
  fireEvent.click(screen.getByRole("button", { name: "试验靶点: EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "查看 NCT01234567 试验详情" }));
  expect(onTrialChange).toHaveBeenCalledWith(trialId);

  fireEvent.click(within(screen.getByRole("columnheader", { name: /注册号与试验/ })).getByRole("button"));
  expect(onSearchChange).toHaveBeenLastCalledWith(
    expect.objectContaining({ sortBy: "registry_id", sortDirection: "asc", offset: 0 }),
  );

  fireEvent.change(screen.getByLabelText("注册平台"), { target: { value: "ClinicalTrials.gov" } });
  fireEvent.change(screen.getByLabelText("招募状态"), { target: { value: "RECRUITING" } });
  fireEvent.change(screen.getByLabelText("临床分期"), { target: { value: "PHASE2" } });
  fireEvent.change(screen.getByLabelText("研究类型"), { target: { value: "INTERVENTIONAL" } });
  fireEvent.change(screen.getByLabelText("试验简称"), { target: { value: "KEYNOTE" } });
  fireEvent.change(screen.getByLabelText("发起类型"), { target: { value: "ist" } });
  fireEvent.change(screen.getByLabelText("治疗线次"), { target: { value: "first_line" } });
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("结果最优评价"), { target: { value: "positive" } });
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "false" } });
  expect(screen.getByLabelText("结果最优评价")).toBeDisabled();
  expect(screen.getByLabelText("结果最优评价")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("结果发布"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("结果最优评价"), { target: { value: "positive" } });
  fireEvent.change(screen.getByLabelText("结果发布日期起"), { target: { value: "2026-01-01" } });
  fireEvent.change(screen.getByLabelText("结果发布日期止"), { target: { value: "2026-07-31" } });
  fireEvent.change(screen.getByLabelText("关键结果"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("发表编号"), { target: { value: "PMID:12345678" } });
  fireEvent.change(screen.getByLabelText("会议"), { target: { value: "ASCO" } });
  fireEvent.change(screen.getByLabelText("披露日期起"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("披露日期止"), { target: { value: "2026-07-31" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(onSearchChange).toHaveBeenLastCalledWith({
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
    resultsPostedFrom: "2026-01-01",
    resultsPostedTo: "2026-07-31",
    investigationalDrug: "",
    combinationDrug: "",
    investigationalTarget: "",
    combinationTarget: "",
    investigationalDrugEntityIds: [],
    combinationDrugEntityIds: [],
    investigationalTargetEntityIds: [],
    combinationTargetEntityIds: [],
    linkedDrugModalities: [],
    linkedDrugInnovationTypes: [],
    linkedDrugCategories: [],
    linkedDrugProgramTags: [],
    linkedDrugGlobalPhase: "",
    linkedDrugOrganizationCountryRegion: "",
    roleEntityId: "",
    roleEntityIds: [],
    roleEntityRole: "",
    hasKeyResult: "true",
    publicationId: "PMID:12345678",
    conference: "ASCO",
    disclosedFrom: "2026-07-01",
    disclosedTo: "2026-07-31",
    sortBy: "last_update_posted",
    sortDirection: "desc",
    displayMode: "list",
    analysisView: "chart",
    offset: 0,
  });

  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenLastCalledWith(
    expect.objectContaining({ query: "EGFR", sortBy: "last_update_posted", sortDirection: "desc", offset: 100 }),
  );
});

it("saves and subscribes the applied clinical trial query", async () => {
  renderWithQueryClient(
    <TrialsView
      displayMode="list"
      initialQuery="EGFR"
      initialRegistry="ClinicalTrials.gov"
      initialStatus="RECRUITING"
      initialPhase="PHASE2"
      initialStudyType="INTERVENTIONAL"
      initialAcronym="KEYNOTE"
      initialInitiationType="ist"
      initialTherapyLine="first_line"
      initialHasResults="true"
      initialResultEvaluation="positive"
      initialResultsPostedFrom="2026-07-01"
      initialResultsPostedTo="2026-07-31"
      initialInvestigationalDrug="VX-101"
      initialCombinationDrug="Pembrolizumab"
      initialInvestigationalTarget="EGFR"
      initialCombinationTarget="PD-1"
      initialInvestigationalDrugEntityIds={[]}
      initialCombinationDrugEntityIds={[]}
      initialInvestigationalTargetEntityIds={[]}
      initialCombinationTargetEntityIds={[]}
      initialLinkedDrugModalities={["antibody"]}
      initialLinkedDrugInnovationTypes={["innovative"]}
      initialLinkedDrugCategories={["biologic"]}
      initialLinkedDrugProgramTags={["first_in_class"]}
      initialLinkedDrugGlobalPhase="phase_3"
      initialLinkedDrugOrganizationCountryRegion="CN"
      initialRoleEntityId=""
      initialRoleEntityIds={[]}
      initialRoleEntityRole=""
      initialHasKeyResult="true"
      initialPublicationId="PMID:12345678"
      initialConference="ASCO"
      initialDisclosedFrom="2026-07-01"
      initialDisclosedTo="2026-07-31"
      initialSortBy="result_evaluation"
      initialSortDirection="asc"
      initialOffset={0}
      selectedTrialId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onTrialChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onDisplayModeChange={vi.fn()}
      analysisView="chart"
      onAnalysisViewChange={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "临床试验结果" });
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  expect(screen.getByRole("dialog", { name: "保存当前临床试验检索" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "EGFR trial results" } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(saveClinicalTrialSearch).toHaveBeenCalledWith(
      {
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
          investigationalDrugEntityIds: [],
          combinationDrugEntityIds: [],
          investigationalTargetEntityIds: [],
          combinationTargetEntityIds: [],
          linkedDrugModalities: ["antibody"],
          linkedDrugInnovationTypes: ["innovative"],
          linkedDrugCategories: ["biologic"],
          linkedDrugProgramTags: ["first_in_class"],
          linkedDrugGlobalPhase: "phase_3",
          linkedDrugOrganizationCountryRegion: "CN",
          roleEntityId: "",
          roleEntityIds: [],
          roleEntityRole: "",
          hasKeyResult: "true",
          publicationId: "PMID:12345678",
          conference: "ASCO",
          disclosedFrom: "2026-07-01",
          disclosedTo: "2026-07-31",
          sortBy: "result_evaluation",
          sortDirection: "asc",
          displayMode: "list",
          analysisView: "chart",
        },
        shared: true,
        monitor: true,
      },
      expect.anything(),
    ),
  );
  expect(await screen.findByText("临床试验检索已保存并启用监控")).toBeVisible();
});

it("renders the trial detail deep link with design, outcomes, history and provenance access", async () => {
  const onTrialChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  function Harness({ contextual = true }: { contextual?: boolean }) {
    const [activeSection, setActiveSection] = useState<"overview" | "design" | "outcomes" | "timeline">("overview");
    return (
      <TrialsView
        displayMode="list"
        initialQuery=""
        initialRegistry=""
        initialStatus=""
        initialPhase=""
        initialStudyType=""
        initialAcronym=""
        initialInitiationType=""
        initialTherapyLine=""
        initialHasResults="true"
        initialResultEvaluation="positive"
        initialResultsPostedFrom="2026-01-01"
        initialResultsPostedTo="2026-07-31"
        initialInvestigationalDrug=""
        initialCombinationDrug=""
        initialInvestigationalTarget=""
        initialCombinationTarget=""
        initialInvestigationalDrugEntityIds={[]}
        initialCombinationDrugEntityIds={[]}
        initialInvestigationalTargetEntityIds={[]}
        initialCombinationTargetEntityIds={[]}
        initialLinkedDrugModalities={[]}
        initialLinkedDrugInnovationTypes={[]}
        initialLinkedDrugCategories={[]}
        initialLinkedDrugProgramTags={[]}
        initialLinkedDrugGlobalPhase=""
        initialLinkedDrugOrganizationCountryRegion=""
        initialRoleEntityId=""
        initialRoleEntityIds={[]}
        initialRoleEntityRole=""
        initialHasKeyResult=""
        initialPublicationId=""
        initialConference=""
        initialDisclosedFrom=""
        initialDisclosedTo=""
        initialSortBy="last_update_posted"
        initialSortDirection="desc"
        initialOffset={0}
        selectedTrialId={trialId}
        activeSection={activeSection}
        onSearchChange={vi.fn()}
        onTrialChange={onTrialChange}
        showListReturn={!contextual}
        onSectionChange={setActiveSection}
        onOpenEntity={onOpenEntity}
        onOpenDrug={onOpenDrug}
        onOpenTarget={onOpenTarget}
        onDisplayModeChange={vi.fn()}
        analysisView="chart"
        onAnalysisViewChange={vi.fn()}
      />
    );
  }
  const view = renderWithQueryClient(<Harness />);

  expect(await screen.findByRole("heading", { name: trialDetail.official_title })).toBeInTheDocument();
  expect(loadTrialDetail).toHaveBeenCalledWith(trialId, expect.any(AbortSignal));
  expect(searchTrials).not.toHaveBeenCalled();
  expect(screen.getByText(/临床试验专业档案/)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "关联药物与靶点" })).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/规范角色|治理来源|授权来源/);
  expect(screen.getByRole("button", { name: `查看 ${trialDetail.registry_id} 的原始证据` })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "试验靶点: EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  fireEvent.click(screen.getByRole("button", { name: "试验药物: VX-101" }));
  expect(onOpenDrug).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440003");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole("tab", { name: "设计与入组" }));
  expect(screen.getByText("Single-arm phase 2 cohort")).toBeInTheDocument();
  expect(screen.getByText("Adults with confirmed EGFR-mutated NSCLC")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "终点与结果" }));
  expect(screen.getByText("Objective response rate")).toBeInTheDocument();
  expect(screen.getByText("42")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "结构化结果：Objective response rate" })).toHaveAttribute("tabindex", "0");
  expect(screen.getByText(/p=0\.01/)).toBeInTheDocument();
  expect(screen.getByText("结果披露与版本")).toBeInTheDocument();
  expect(screen.getByText(/PMID:12345678/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "时间线与中心" }));
  expect(screen.getByText("Shanghai Oncology Center")).toBeInTheDocument();
  expect(screen.getByText("First site opened")).toBeInTheDocument();
  expect(screen.getByText("来源记录已收录")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "返回试验列表" })).not.toBeInTheDocument();
  expect(onTrialChange).not.toHaveBeenCalledWith(null);

  view.rerender(<Harness contextual={false} />);
  fireEvent.click(screen.getByRole("button", { name: "返回试验列表" }));
  expect(onTrialChange).toHaveBeenCalledWith(null);
});

it("renders the explicit empty state and clears active filters", async () => {
  vi.mocked(searchTrials).mockResolvedValue({
    ...trialResult,
    items: [],
    total: 0,
    facets: {},
    applied_filters: [{ field: "query", operator: "contains", value: "missing" }],
  });
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <TrialsView
      displayMode="list"
      initialQuery="missing"
      initialRegistry="ClinicalTrials.gov"
      initialStatus=""
      initialPhase=""
      initialStudyType=""
      initialAcronym=""
      initialInitiationType=""
      initialTherapyLine=""
      initialHasResults=""
      initialResultEvaluation=""
      initialResultsPostedFrom=""
      initialResultsPostedTo=""
      initialInvestigationalDrug=""
      initialCombinationDrug=""
      initialInvestigationalTarget=""
      initialCombinationTarget=""
      initialInvestigationalDrugEntityIds={[]}
      initialCombinationDrugEntityIds={[]}
      initialInvestigationalTargetEntityIds={[]}
      initialCombinationTargetEntityIds={[]}
      initialLinkedDrugModalities={[]}
      initialLinkedDrugInnovationTypes={[]}
      initialLinkedDrugCategories={[]}
      initialLinkedDrugProgramTags={[]}
      initialLinkedDrugGlobalPhase=""
      initialLinkedDrugOrganizationCountryRegion=""
      initialRoleEntityId=""
      initialRoleEntityIds={[]}
      initialRoleEntityRole=""
      initialHasKeyResult=""
      initialPublicationId=""
      initialConference=""
      initialDisclosedFrom=""
      initialDisclosedTo=""
      initialSortBy="last_update_posted"
      initialSortDirection="desc"
      initialOffset={0}
      selectedTrialId={null}
      activeSection="overview"
      onSearchChange={onSearchChange}
      onTrialChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onDisplayModeChange={vi.fn()}
      analysisView="chart"
      onAnalysisViewChange={vi.fn()}
    />,
  );

  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("聚合注册平台的试验设计、状态、分期、适应症、干预和申办方，并关联药物与靶点信息。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "试验药物（任一）多选" })).toBeInTheDocument();
  fireEvent.click(screen.getByText("联用药物与靶点"));
  expect(screen.getByRole("group", { name: "联用药物（任一）多选" })).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/规范实体|规范试验|规范联用|覆盖边界/);
  const saveEmptyQuery = screen.getByRole("button", { name: "保存/订阅" });
  expect(saveEmptyQuery).toBeEnabled();
  fireEvent.click(saveEmptyQuery);
  expect(screen.getByRole("dialog", { name: "保存当前临床试验检索" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() =>
    expect(onSearchChange).toHaveBeenLastCalledWith({
      query: "",
      registry: "",
      status: "",
      phase: "",
      studyType: "",
      acronym: "",
      initiationType: "",
      therapyLine: "",
      hasResults: "",
      resultEvaluation: "",
      resultsPostedFrom: "",
      resultsPostedTo: "",
      investigationalDrug: "",
      combinationDrug: "",
      investigationalTarget: "",
      combinationTarget: "",
      investigationalDrugEntityIds: [],
      combinationDrugEntityIds: [],
      investigationalTargetEntityIds: [],
      combinationTargetEntityIds: [],
      linkedDrugModalities: [],
      linkedDrugInnovationTypes: [],
      linkedDrugCategories: [],
      linkedDrugProgramTags: [],
      linkedDrugGlobalPhase: "",
      linkedDrugOrganizationCountryRegion: "",
      roleEntityId: "",
      roleEntityIds: [],
      roleEntityRole: "",
      hasKeyResult: "",
      publicationId: "",
      conference: "",
      disclosedFrom: "",
      disclosedTo: "",
      sortBy: "last_update_posted",
      sortDirection: "desc",
      displayMode: "list",
      analysisView: "chart",
      offset: 0,
    }),
  );
});

it("renders a recoverable trial query error", async () => {
  vi.mocked(searchTrials).mockRejectedValue(new Error("Trial registry unavailable"));
  renderWithQueryClient(
    <TrialsView
      displayMode="list"
      initialQuery=""
      initialRegistry=""
      initialStatus=""
      initialPhase=""
      initialStudyType=""
      initialAcronym=""
      initialInitiationType=""
      initialTherapyLine=""
      initialHasResults=""
      initialResultEvaluation=""
      initialResultsPostedFrom=""
      initialResultsPostedTo=""
      initialInvestigationalDrug=""
      initialCombinationDrug=""
      initialInvestigationalTarget=""
      initialCombinationTarget=""
      initialInvestigationalDrugEntityIds={[]}
      initialCombinationDrugEntityIds={[]}
      initialInvestigationalTargetEntityIds={[]}
      initialCombinationTargetEntityIds={[]}
      initialLinkedDrugModalities={[]}
      initialLinkedDrugInnovationTypes={[]}
      initialLinkedDrugCategories={[]}
      initialLinkedDrugProgramTags={[]}
      initialLinkedDrugGlobalPhase=""
      initialLinkedDrugOrganizationCountryRegion=""
      initialRoleEntityId=""
      initialRoleEntityIds={[]}
      initialRoleEntityRole=""
      initialHasKeyResult=""
      initialPublicationId=""
      initialConference=""
      initialDisclosedFrom=""
      initialDisclosedTo=""
      initialSortBy="last_update_posted"
      initialSortDirection="desc"
      initialOffset={0}
      selectedTrialId={null}
      activeSection="overview"
      onSearchChange={vi.fn()}
      onTrialChange={vi.fn()}
      onSectionChange={vi.fn()}
      onOpenEntity={vi.fn()}
      onDisplayModeChange={vi.fn()}
      analysisView="chart"
      onAnalysisViewChange={vi.fn()}
    />,
  );

  expect(await screen.findByText("Trial registry unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});
