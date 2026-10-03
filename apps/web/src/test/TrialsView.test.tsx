import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { loadTrialDetail, saveClinicalTrialSearch, searchTrials } from "../lib/contracts/trials";
import type { ClinicalTrialDetailRead, ClinicalTrialSearchResult } from "../lib/generated";
import { TrialsView } from "../views/TrialsView";
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

const trialId = "c3f40269-f4c3-4f52-a052-3d6f633e67af";

const trialDetail: ClinicalTrialDetailRead = {
  id: trialId,
  entity_id: "550e8400-e29b-41d4-a716-446655440001",
  registry_id: "NCT01234567",
  registry_name: "ClinicalTrials.gov",
  official_title: "A Phase 2 Study of VX-101 in EGFR-mutated NSCLC",
  acronym: "KEYNOTE-VX101",
  initiation_type: "ist",
  therapy_lines: ["first_line"],
  overall_status: "RECRUITING",
  phases: ["PHASE2"],
  study_type: "INTERVENTIONAL",
  conditions: ["Non-small Cell Lung Cancer"],
  interventions: [
    {
      name: "VX-101",
      type: "DRUG",
      arm_labels: ["VX-101 cohort"],
      description: "Oral targeted therapy",
      other_names: [],
    },
  ],
  sponsors: [{ name: "Victor Therapeutics", sponsor_class: "INDUSTRY" }],
  locations: [
    {
      country: "China",
      city: "Shanghai",
      facility: "Shanghai Oncology Center",
      state: null,
      status: "RECRUITING",
    },
  ],
  outcomes: [
    {
      outcome_type: "PRIMARY",
      measure: "Objective response rate",
      time_frame: "24 weeks",
      description: "Confirmed response by independent review",
      results: [
        {
          group_label: "VX-101 cohort",
          value: "42",
          unit: "%",
          participants: 120,
          lower_limit: 33.1,
          upper_limit: 51.4,
          dispersion: null,
        },
      ],
      statistical_analyses: [
        {
          method: "Exact binomial",
          p_value: "0.01",
          parameter_type: "response_rate",
          parameter_value: 42,
          confidence_interval_percent: 95,
          lower_limit: 33.1,
          upper_limit: 51.4,
          notes: null,
        },
      ],
    },
  ],
  arms: [
    {
      label: "VX-101 cohort",
      type: "EXPERIMENTAL",
      description: "VX-101 once daily",
      intervention_names: ["VX-101"],
    },
  ],
  study_design: {
    allocation: "NON_RANDOMIZED",
    intervention_model: "SINGLE_GROUP",
    intervention_model_description: "Single-arm phase 2 cohort",
    masking: "NONE",
    masking_description: null,
    observational_model: null,
    primary_purpose: "TREATMENT",
    time_perspective: null,
    who_masked: [],
  },
  eligibility: {
    criteria: "Adults with confirmed EGFR-mutated NSCLC",
    minimum_age: "18 Years",
    maximum_age: "80 Years",
    sex: "ALL",
    healthy_volunteers: false,
    gender_based: false,
    sampling_method: null,
  },
  status_history: [
    {
      status: "NOT_YET_RECRUITING",
      effective_at: "2025-12-01T00:00:00Z",
      reason: "Initial registration",
      source_document_id: "7d478f88-b85b-4f35-90f1-e1bb786ec8bb",
    },
    {
      status: "RECRUITING",
      effective_at: "2026-01-01T00:00:00Z",
      reason: "First site opened",
      source_document_id: "7d478f88-b85b-4f35-90f1-e1bb786ec8bb",
    },
  ],
  enrollment: 126,
  start_date: "2026-01-01",
  start_date_precision: "day",
  completion_date: null,
  completion_date_precision: null,
  results_first_posted: "2026-07-18T00:00:00Z",
  last_update_posted: "2026-07-20T00:00:00Z",
  has_results: true,
  result_evaluation: "positive",
  source_document_id: "7d478f88-b85b-4f35-90f1-e1bb786ec8bb",
  linked_entities: [
    { id: "550e8400-e29b-41d4-a716-446655440002", name: "EGFR", entity_type: "target" },
    { id: "550e8400-e29b-41d4-a716-446655440003", name: "VX-101", entity_type: "drug" },
  ],
  entity_roles: [
    {
      entity_id: "550e8400-e29b-41d4-a716-446655440003",
      name: "VX-101",
      entity_type: "drug",
      role: "investigational_drug",
    },
    {
      entity_id: "550e8400-e29b-41d4-a716-446655440002",
      name: "EGFR",
      entity_type: "target",
      role: "investigational_target",
    },
  ],
  key_result_count: 1,
  latest_result_disclosure: {
    id: "b3f40269-f4c3-4f52-a052-3d6f633e67af",
    disclosure_key: "trial-1",
    version: 2,
    disclosure_type: "journal_article",
    external_id: "PMID:12345678",
    title: "VX-101 Phase 2 results",
    disclosed_at: "2026-07-19T00:00:00Z",
    conference_name: null,
    is_key_result: true,
    result_evaluation: "positive",
    source_locator: "page 12",
    source_quote: "VX-101 demonstrated a 42% response rate.",
    source_document_id: "7d478f88-b85b-4f35-90f1-e1bb786ec8bb",
  },
  result_disclosures: [
    {
      id: "b3f40269-f4c3-4f52-a052-3d6f633e67af",
      disclosure_key: "trial-1",
      version: 2,
      disclosure_type: "journal_article",
      external_id: "PMID:12345678",
      title: "VX-101 Phase 2 results",
      disclosed_at: "2026-07-19T00:00:00Z",
      conference_name: null,
      is_key_result: true,
      result_evaluation: "positive",
      source_locator: "page 12",
      source_quote: "VX-101 demonstrated a 42% response rate.",
      source_document_id: "7d478f88-b85b-4f35-90f1-e1bb786ec8bb",
    },
  ],
};

const trialResult: ClinicalTrialSearchResult = {
  items: [trialDetail],
  total: 101,
  limit: 100,
  offset: 0,
  facets: {
    registry: { "ClinicalTrials.gov": 101 },
    overall_status: { RECRUITING: 101 },
    phase: { PHASE2: 101 },
    study_type: { INTERVENTIONAL: 101 },
    initiation_type: { ist: 101 },
    therapy_line: { first_line: 101 },
    has_results: { true: 100, false: 1 },
    result_evaluation: { positive: 100 },
    has_key_result: { true: 100 },
  },
  landscape: {
    total_trials: 101,
    publication_year_phase: [
      { key: "2026", total: 100, values: { PHASE2: 100 } },
      { key: "__missing__", total: 1, values: { PHASE2: 1 } },
    ],
    phase_evaluation: [{ key: "PHASE2", total: 101, values: { positive: 100, __missing__: 1 } }],
  },
  as_of: "2026-07-22T10:00:00Z",
  query_schema_version: "pharma.clinical_trial.search.v10",
  sort_by: "last_update_posted",
  sort_direction: "desc",
  applied_filters: [
    { field: "q", operator: "contains", value: "EGFR" },
    { field: "result_evaluation", operator: "eq", value: "positive" },
  ],
  warnings: ["结果受当前数据授权、注册平台时效和治理状态限制。"],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(searchTrials).mockResolvedValue(trialResult);
  vi.mocked(loadTrialDetail).mockResolvedValue(trialDetail);
  vi.mocked(saveClinicalTrialSearch).mockResolvedValue({ message: "临床试验检索已保存并启用监控" });
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
