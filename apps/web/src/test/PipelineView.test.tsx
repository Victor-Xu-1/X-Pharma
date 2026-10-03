import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { emptyPipelineSearchFilters, savePipelineSearch, searchPipelines } from "../lib/contracts/pipeline";
import { PipelineView } from "../views/PipelineView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/pipeline", async () => {
  const actual = await vi.importActual<typeof import("../lib/contracts/pipeline")>("../lib/contracts/pipeline");
  return {
    ...actual,
    pipelineKeys: { search: (filters: unknown) => ["pipelines", filters] },
    searchPipelines: vi.fn(),
    savePipelineSearch: vi.fn(),
  };
});

const initialFilters = { ...emptyPipelineSearchFilters(), query: "EGFR" };
const pipelineResult = {
  items: [
    {
      id: "program-1",
      drug_entity_id: "drug-1",
      drug_name: "VX-101",
      target_entity_id: "target-1",
      target_name: "EGFR",
      targets: [
        { entity_id: "target-1", name: "EGFR", role: "primary" as const, position: 0 },
        { entity_id: "target-2", name: "ERBB2", role: "combination" as const, position: 1 },
      ],
      target_combination_key: "550e8400-e29b-41d4-a716-446655440000|550e8400-e29b-41d4-a716-446655440001",
      disease_entity_id: "disease-1",
      disease_name: "NSCLC",
      organization_entity_id: "organization-1",
      organization_name: "Victor Therapeutics",
      organizations: [
        {
          entity_id: "organization-1",
          name: "Victor Therapeutics",
          role: "originator" as const,
          country_region: "CN",
          organization_type: "biopharma",
          position: 0,
        },
        {
          entity_id: "organization-2",
          name: "Partner Bio",
          role: "collaborator" as const,
          country_region: "US",
          organization_type: "biotech",
          position: 1,
        },
      ],
      modality: "small molecule",
      mechanism_of_action: "covalent inhibitor",
      phase: "phase_2",
      status_detail: "active",
      program_status: "active" as const,
      status_date: "2026-07-01T00:00:00Z",
      geography: "Global",
      global_phase: "phase_2",
      china_phase: "phase_1",
      global_phase_started_at: "2026-06-01T00:00:00Z",
      china_phase_started_at: "2025-03-01T00:00:00Z",
      development_rights_regions: ["Global"],
      commercialization_rights_regions: ["Greater China"],
      program_tags: ["ChEMBL", "maximum clinical phase 2", "first_in_class"],
      status_history: [],
      milestones: [
        {
          milestone_type: "first_patient_in",
          title: "Global Phase II first patient in",
          occurred_at: "2026-06-15T00:00:00Z",
        },
      ],
      clinical_trial_count: 3,
      has_clinical_results: true,
      clinical_result_evaluations: ["positive" as const],
      deal_count: 2,
      deal_currencies: ["USD"],
      source_document_id: "document-1",
    },
  ],
  total: 101,
  limit: 20,
  offset: 0,
  facets: {
    modality: { "small molecule": 101 },
    phase: { phase_2: 101 },
    geography: { Global: 101 },
    global_phase: { phase_2: 101 },
    china_phase: { phase_1: 101 },
    development_rights_region: { Global: 101 },
    commercialization_rights_region: { "Greater China": 101 },
    program_tag: { ChEMBL: 101, "maximum clinical phase 2": 101, first_in_class: 101 },
    milestone_type: { first_patient_in: 101 },
    has_clinical_results: { true: 72, false: 29 },
    clinical_result_evaluation: { positive: 42 },
    has_deal: { true: 63, false: 38 },
    deal_currency: { USD: 51 },
    organization_role: { originator: 101, collaborator: 35 },
    organization_type: { biopharma: 101, biotech: 35 },
    organization_country_region: { CN: 101, US: 35 },
  },
  landscape: {
    total_programs: 101,
    distinct_drugs: 87,
    distinct_targets: 1,
    distinct_diseases: 4,
    distinct_organizations: 12,
    limit: 8,
    stage_scope: "overall" as const,
    target_aggregation: "all" as const,
    overall_phase: [{ key: "phase_2", label: "phase_2", count: 101, share: 1, entity_id: null }],
    global_phase: [{ key: "phase_2", label: "phase_2", count: 101, share: 1, entity_id: null }],
    china_phase: [{ key: "phase_1", label: "phase_1", count: 64, share: 0.633663, entity_id: null }],
    targets: [
      {
        key: "target-1",
        label: "EGFR",
        count: 101,
        share: 1,
        entity_id: "target-1",
        phase_counts: { phase_2: 81, phase_1: 20 },
      },
    ],
    diseases: [{ key: "disease-1", label: "NSCLC", count: 78, share: 0.772277, entity_id: "disease-1" }],
    target_combinations: [
      {
        key: "550e8400-e29b-41d4-a716-446655440000|550e8400-e29b-41d4-a716-446655440001",
        label: "EGFR + ERBB2",
        count: 24,
        share: 0.237624,
        entity_id: null,
      },
    ],
    modality: [{ key: "small molecule", label: "small molecule", count: 101, share: 1, entity_id: null }],
    geography: [{ key: "Global", label: "Global", count: 101, share: 1, entity_id: null }],
    organizations: [
      {
        key: "organization-1",
        label: "Victor Therapeutics",
        count: 35,
        share: 0.346535,
        entity_id: "organization-1",
      },
    ],
  },
  as_of: "2026-07-24T10:00:00Z",
  query_schema_version: "pharma.pipeline.search.v13",
  sort_by: "status_date" as const,
  sort_direction: "desc" as const,
  applied_filters: [{ field: "q", operator: "contains" as const, value: "EGFR" }],
  warnings: ["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"],
};

beforeEach(() => {
  vi.mocked(searchPipelines).mockResolvedValue(pipelineResult);
  vi.mocked(savePipelineSearch).mockResolvedValue({ message: "管线检索已保存并启用监控" });
});

const defaultAnalysisProps = {
  resultGrain: "program" as const,
  analysisDimension: "all" as const,
  analysisView: "chart" as const,
  analysisLimit: 8 as const,
  analysisStageScope: "overall" as const,
  targetAggregation: "all" as const,
  onResultGrainChange: vi.fn(),
  onAnalysisChange: vi.fn(),
  onOpenTrialsForDrug: vi.fn(),
  onOpenDealsForDrug: vi.fn(),
};

it("preserves an unsubmitted filter draft when a parent recreates the same applied filter object", async () => {
  const props = {
    ...defaultAnalysisProps,
    displayMode: "list" as const,
    initialFilters,
    onSearchChange: vi.fn(),
    onDisplayModeChange: vi.fn(),
    onOpenDrug: vi.fn(),
    onOpenEntity: vi.fn(),
  };
  const { rerender } = renderWithQueryClient(<PipelineView {...props} />);
  await screen.findByRole("table", { name: "药物与研发管线结果" });
  const keyword = screen.getByLabelText("关键词");
  fireEvent.change(keyword, { target: { value: "unsubmitted draft" } });
  rerender(<PipelineView {...props} initialFilters={{ ...initialFilters }} />);
  expect(keyword).toHaveValue("unsubmitted draft");
  expect(searchPipelines).toHaveBeenCalledTimes(1);
});

it("submits regional phase, rights and date filters and opens linked entities", async () => {
  const onSearchChange = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  const onOpenTrialsForDrug = vi.fn();
  const onOpenDealsForDrug = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="list"
      initialFilters={initialFilters}
      onSearchChange={onSearchChange}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={onOpenDrug}
      onOpenEntity={onOpenEntity}
      onOpenTarget={onOpenTarget}
      onOpenDisease={onOpenDisease}
      onOpenOrganization={onOpenOrganization}
      onOpenTrialsForDrug={onOpenTrialsForDrug}
      onOpenDealsForDrug={onOpenDealsForDrug}
    />,
  );

  const resultsTable = await screen.findByRole("table", { name: "药物与研发管线结果" });
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|来源授权/);
  expect(searchPipelines).toHaveBeenCalledWith(
    initialFilters,
    { limit: 8, stageScope: "overall", targetAggregation: "all" },
    expect.any(AbortSignal),
    "program",
  );
  expect(screen.getByText(/全部结果按状态日期降序/)).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /状态日期/ })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  expect(within(resultsTable).getByText("EGFR")).toBeInTheDocument();
  expect(within(resultsTable).getByText("ERBB2")).toBeInTheDocument();
  expect(within(resultsTable).getByText("Partner Bio")).toBeInTheDocument();
  expect(within(resultsTable).getByText("合作方", { exact: false })).toBeInTheDocument();
  expect(within(resultsTable).getByText("Greater China", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "进行中 (0)" })).toBeDisabled();
  expect(screen.getByRole("option", { name: "已停止 (0)" })).toBeDisabled();
  expect(within(resultsTable).getByRole("columnheader", { name: /作用机制/ })).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /药物类型/ })).toBeVisible();
  expect(within(resultsTable).getByText("小分子")).toBeInTheDocument();
  expect(within(resultsTable).getByText("First-in-Class")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/ChEMBL|maximum clinical phase/i);
  expect(within(resultsTable).getByRole("columnheader", { name: /总体阶段/ })).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /项目状态/ })).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /记录地区/ })).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /全球阶段起始/ })).toBeVisible();
  expect(within(resultsTable).getByRole("columnheader", { name: /中国阶段起始/ })).toBeVisible();
  expect(within(resultsTable).getByText("covalent inhibitor")).toBeInTheDocument();
  expect(within(resultsTable).getByText("进行中")).toBeInTheDocument();
  // Ungoverned free text must never be rendered as if it were a known state: the badge
  // shows the governed vocabulary only, and the raw detail stays visible as context.
  expect(within(resultsTable).queryByText("paused pending partner decision")).not.toBeInTheDocument();
  expect(within(resultsTable).getByText("2026/06/01")).toBeInTheDocument();
  expect(within(resultsTable).getByText("2025/03/01")).toBeInTheDocument();
  expect(within(resultsTable).getByText("Global Phase II first patient in")).toBeInTheDocument();
  expect(within(resultsTable).getByText("3 项试验")).toBeInTheDocument();
  expect(within(resultsTable).getByText("2 笔交易")).toBeInTheDocument();
  fireEvent.click(within(resultsTable).getByRole("button", { name: "查看 VX-101 的 3 项临床试验" }));
  expect(onOpenTrialsForDrug).toHaveBeenCalledWith("drug-1");
  fireEvent.click(within(resultsTable).getByRole("button", { name: "查看 VX-101 的 2 笔交易" }));
  expect(onOpenDealsForDrug).toHaveBeenCalledWith("drug-1");
  fireEvent.click(screen.getByRole("button", { name: "打开 VX-101 档案" }));
  expect(onOpenDrug).toHaveBeenCalledWith("drug-1");
  fireEvent.click(within(resultsTable).getByRole("button", { name: "EGFR" }));
  expect(onOpenTarget).toHaveBeenCalledWith("target-1");
  expect(onOpenEntity).not.toHaveBeenCalled();
  fireEvent.click(within(resultsTable).getByRole("button", { name: "NSCLC" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-1");
  fireEvent.click(within(resultsTable).getByRole("button", { name: "Partner Bio" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("organization-2");

  const drugHeader = within(resultsTable).getByRole("columnheader", { name: "药物" });
  fireEvent.click(within(drugHeader).getByRole("button"));
  expect(onSearchChange).toHaveBeenCalledWith({
    ...initialFilters,
    sortBy: "drug_name",
    sortDirection: "asc",
    sort: [{ field: "drug_name", direction: "asc" }],
    offset: 0,
  });

  const mechanismHeader = within(resultsTable).getByRole("columnheader", { name: /作用机制/ });
  fireEvent.click(within(mechanismHeader).getByRole("button"));
  expect(onSearchChange).toHaveBeenCalledWith({
    ...initialFilters,
    sortBy: "mechanism_of_action",
    sortDirection: "asc",
    sort: [{ field: "mechanism_of_action", direction: "asc" }],
    offset: 0,
  });

  fireEvent.click(screen.getByText("机构、区域阶段、权益与里程碑"));
  fireEvent.change(screen.getByLabelText("机构角色"), { target: { value: "collaborator" } });
  fireEvent.change(screen.getByLabelText("机构类型"), { target: { value: "biotech" } });
  fireEvent.change(screen.getByLabelText("机构所在地区"), { target: { value: "US" } });
  fireEvent.change(screen.getByLabelText("全球最高阶段"), { target: { value: "phase_2" } });
  fireEvent.change(screen.getByLabelText("中国最高阶段"), { target: { value: "phase_1" } });
  fireEvent.change(screen.getByLabelText("研发权益地区"), { target: { value: "Global" } });
  fireEvent.change(screen.getByLabelText("商业化权益地区"), { target: { value: "Greater China" } });
  fireEvent.click(screen.getByLabelText("项目标签：全部"));
  fireEvent.click(screen.getByRole("checkbox", { name: /First-in-Class/ }));
  fireEvent.change(screen.getByLabelText("里程碑类型"), { target: { value: "first_patient_in" } });
  const globalRange = screen.getByRole("group", { name: "全球阶段起始日期" });
  fireEvent.change(within(globalRange).getByLabelText("起"), { target: { value: "2026-01-01" } });
  fireEvent.change(within(globalRange).getByLabelText("止"), { target: { value: "2026-07-31" } });
  const milestoneRange = screen.getByRole("group", { name: "里程碑日期" });
  fireEvent.change(within(milestoneRange).getByLabelText("起"), { target: { value: "2026-06-01" } });
  fireEvent.change(within(milestoneRange).getByLabelText("止"), { target: { value: "2026-06-30" } });
  fireEvent.click(screen.getByText("临床结果与交易信号"));
  fireEvent.change(screen.getByLabelText("是否已有临床结果"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("临床结果评价"), { target: { value: "positive" } });
  fireEvent.change(screen.getByLabelText("是否存在交易记录"), { target: { value: "true" } });
  fireEvent.change(screen.getByLabelText("交易币种"), { target: { value: "USD" } });
  fireEvent.change(screen.getByLabelText("潜在总额下限"), { target: { value: "400000000" } });
  fireEvent.change(screen.getByLabelText("潜在总额上限"), { target: { value: "600000000" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));

  expect(onSearchChange).toHaveBeenCalledWith({
    ...initialFilters,
    organizationRole: "collaborator",
    organizationType: "biotech",
    organizationCountryRegion: "US",
    globalPhase: "phase_2",
    chinaPhase: "phase_1",
    globalPhaseStartedFrom: "2026-01-01",
    globalPhaseStartedTo: "2026-07-31",
    developmentRightsRegion: "Global",
    commercializationRightsRegion: "Greater China",
    programTags: ["first_in_class"],
    milestoneType: "first_patient_in",
    milestoneFrom: "2026-06-01",
    milestoneTo: "2026-06-30",
    hasClinicalResults: "true",
    clinicalResultEvaluation: "positive",
    hasDeal: "true",
    dealCurrency: "USD",
    dealTotalPotentialAmountMin: "400000000",
    dealTotalPotentialAmountMax: "600000000",
  });

  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenCalledWith({ ...initialFilters, offset: 20 });
});

it("distinguishes unique drugs from development projects and switches result grain", async () => {
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    total: 76,
    project_total: 81,
    result_grain: "drug",
  });
  const onResultGrainChange = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      resultGrain="drug"
      onResultGrainChange={onResultGrainChange}
      displayMode="list"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("个药物")).toBeInTheDocument();
  expect(screen.getByText("覆盖 81 条研发项目", { exact: false })).toBeInTheDocument();
  expect(searchPipelines).toHaveBeenLastCalledWith(
    initialFilters,
    { limit: 8, stageScope: "overall", targetAggregation: "all" },
    expect.any(AbortSignal),
    "drug",
  );
  fireEvent.click(screen.getByRole("button", { name: "按项目" }));
  expect(onResultGrainChange).toHaveBeenCalledWith("program");
});

it("uses the aggregate project count instead of repeating an empty tag placeholder", async () => {
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    items: [{ ...pipelineResult.items[0], program_tags: [], project_count: 6 }],
    total: 1,
    project_total: 6,
    result_grain: "drug",
  });
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      resultGrain="drug"
      displayMode="list"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("6 个研发项目")).toBeInTheDocument();
  expect(screen.queryByText("暂无项目标签")).not.toBeInTheDocument();
});

it("renders aggregated drug modalities, mechanisms and distinct indication links from the wire contract", async () => {
  const onOpenDisease = vi.fn();
  const indication = {
    program_id: "program-1",
    disease_entity_id: "disease-1",
    disease_name: "NSCLC",
    phase: "phase_2",
    global_phase: "phase_2",
    china_phase: null,
    global_phase_started_at: null,
    china_phase_started_at: null,
    program_status: "active" as const,
    status_date: null,
    geography: "Global",
  };
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    result_grain: "drug",
    items: [
      {
        ...pipelineResult.items[0],
        modality: null,
        mechanism_of_action: null,
        disease_entity_id: null,
        disease_name: null,
        modalities: ["small molecule", "antibody"],
        mechanisms_of_action: ["covalent inhibitor", "ligand blocking"],
        indications: [
          indication,
          { ...indication, program_id: "program-2" },
          { ...indication, program_id: "program-3", disease_entity_id: "disease-2", disease_name: "Melanoma" },
        ],
      },
    ],
  });
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      resultGrain="drug"
      displayMode="list"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenDisease={onOpenDisease}
    />,
  );
  const results = await screen.findByRole("table", { name: "药物与研发管线结果" });
  expect(results).toHaveTextContent("covalent inhibitor");
  expect(results).toHaveTextContent("ligand blocking");
  expect(results).toHaveTextContent("小分子");
  expect(results).toHaveTextContent("抗体");
  expect(within(results).getAllByRole("button", { name: "NSCLC" })).toHaveLength(1);
  fireEvent.click(within(results).getByRole("button", { name: "Melanoma" }));
  expect(onOpenDisease).toHaveBeenCalledWith("disease-2");
});

it("uses clear Chinese copy when linked disease or organization data is not disclosed", async () => {
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    items: [
      {
        ...pipelineResult.items[0],
        target_entity_id: null,
        target_name: null,
        targets: [],
        disease_entity_id: null,
        disease_name: null,
        organization_entity_id: null,
        organization_name: null,
        organizations: [],
      },
    ],
    total: 1,
  });
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="list"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByRole("table", { name: "药物与研发管线结果" })).toBeInTheDocument();
  expect(screen.getAllByText("未披露")).toHaveLength(3);
});

it("renders the explicit empty state and clears active filters", async () => {
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    items: [],
    total: 0,
    facets: {},
    applied_filters: [{ field: "query", operator: "contains", value: "missing" }],
  });
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="list"
      initialFilters={{ ...initialFilters, query: "missing" }}
      onSearchChange={onSearchChange}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(
    screen.getByText("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"),
  ).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "药品、靶点、适应症与研发机构" })).toBeInTheDocument();
  expect(
    screen.getByText("按药品、靶点、适应症、研发机构、全球与中国阶段、权益地区及里程碑组合查询。"),
  ).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/规范实体|治理状态|覆盖边界/);
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() => expect(onSearchChange).toHaveBeenCalledWith(emptyPipelineSearchFilters()));
});

it("blocks contradictory signal filters before issuing a query", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="list"
      initialFilters={emptyPipelineSearchFilters()}
      onSearchChange={onSearchChange}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  await screen.findByRole("table", { name: "药物与研发管线结果" });
  fireEvent.click(screen.getByText("临床结果与交易信号"));
  fireEvent.change(screen.getByLabelText("潜在总额下限"), { target: { value: "100000000" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));

  expect(screen.getByRole("alert")).toHaveTextContent("按交易金额查询时必须选择币种");
  expect(onSearchChange).not.toHaveBeenCalled();
});

it("renders a recoverable query error", async () => {
  vi.mocked(searchPipelines).mockRejectedValue(new Error("Pipeline service unavailable"));
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="list"
      initialFilters={emptyPipelineSearchFilters()}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("Pipeline service unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("shares the governed query with an interactive competition landscape", async () => {
  const onSearchChange = vi.fn();
  const onDisplayModeChange = vi.fn();
  const onAnalysisChange = vi.fn();
  const onOpenEntity = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="landscape"
      onAnalysisChange={onAnalysisChange}
      initialFilters={initialFilters}
      onSearchChange={onSearchChange}
      onDisplayModeChange={onDisplayModeChange}
      onOpenDrug={vi.fn()}
      onOpenEntity={onOpenEntity}
    />,
  );

  const landscape = await screen.findByLabelText("管线竞争格局");
  expect(within(landscape).getByText("87")).toBeInTheDocument();
  expect(
    await within(landscape).findByRole("img", { name: "药物类型项目数量分布" }, { timeout: 5_000 }),
  ).toBeInTheDocument();
  expect(await within(landscape).findByRole("img", { name: "靶点项目数量分布" })).toBeInTheDocument();
  expect(await within(landscape).findByRole("img", { name: "靶点组合项目数量分布" })).toBeInTheDocument();
  expect(await within(landscape).findByRole("img", { name: "适应症项目数量分布" })).toBeInTheDocument();
  fireEvent.change(within(landscape).getByLabelText("分析维度"), { target: { value: "targets" } });
  expect(onAnalysisChange).toHaveBeenCalledWith({
    dimension: "targets",
    view: "chart",
    limit: 8,
    stageScope: "overall",
    targetAggregation: "all",
  });
  fireEvent.click(within(landscape).getByRole("button", { name: "表格" }));
  expect(onAnalysisChange).toHaveBeenCalledWith({
    dimension: "all",
    view: "table",
    limit: 8,
    stageScope: "overall",
    targetAggregation: "all",
  });
  fireEvent.change(within(landscape).getByLabelText("分析显示范围"), { target: { value: "20" } });
  expect(onAnalysisChange).toHaveBeenCalledWith({
    dimension: "all",
    view: "chart",
    limit: 20,
    stageScope: "overall",
    targetAggregation: "all",
  });
  fireEvent.change(within(landscape).getByLabelText("阶段分析口径"), { target: { value: "global" } });
  expect(onAnalysisChange).toHaveBeenCalledWith({
    dimension: "all",
    view: "chart",
    limit: 8,
    stageScope: "global",
    targetAggregation: "all",
  });
  fireEvent.change(within(landscape).getByLabelText("靶点聚合口径"), { target: { value: "primary" } });
  expect(onAnalysisChange).toHaveBeenCalledWith({
    dimension: "all",
    view: "chart",
    limit: 8,
    stageScope: "overall",
    targetAggregation: "primary",
  });
  fireEvent.click(within(landscape).getByTitle("按EGFR筛选"));
  expect(onSearchChange).toHaveBeenCalledWith({ ...initialFilters, targetEntityId: "target-1", offset: 0 });
  fireEvent.click(within(landscape).getByTitle("按EGFR + ERBB2筛选"));
  expect(onSearchChange).toHaveBeenCalledWith({
    ...initialFilters,
    targetCombinationKey: "550e8400-e29b-41d4-a716-446655440000|550e8400-e29b-41d4-a716-446655440001",
    offset: 0,
  });
  fireEvent.click(within(landscape).getByRole("button", { name: "打开NSCLC档案" }));
  expect(onOpenEntity).toHaveBeenCalledWith("disease-1");
  fireEvent.click(within(landscape).getByTitle("按小分子筛选"));
  expect(onSearchChange).toHaveBeenCalledWith({ ...initialFilters, modalities: ["small molecule"], offset: 0 });
  fireEvent.click(within(landscape).getByRole("button", { name: "打开Victor Therapeutics档案" }));
  expect(onOpenEntity).toHaveBeenCalledWith("organization-1");
  expect(screen.getByText("导出")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "列表" }));
  expect(onDisplayModeChange).toHaveBeenCalledWith("list");
});

it("renders a URL-owned focused analysis as a bounded accessible table", async () => {
  const onSearchChange = vi.fn();
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="landscape"
      analysisDimension="targets"
      analysisView="table"
      analysisLimit={5}
      initialFilters={initialFilters}
      onSearchChange={onSearchChange}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  const landscape = await screen.findByLabelText("管线竞争格局");
  expect(within(landscape).getByLabelText("分析维度")).toHaveValue("targets");
  expect(within(landscape).getByRole("button", { name: "表格" })).toHaveAttribute("aria-pressed", "true");
  expect(within(landscape).getByLabelText("分析显示范围")).toHaveValue("5");
  expect(within(landscape).getByLabelText("阶段分析口径")).toHaveValue("overall");
  expect(within(landscape).getByLabelText("靶点聚合口径")).toHaveValue("all");
  const table = within(landscape).getByRole("table", { name: "靶点统计表" });
  expect(within(table).getByRole("rowheader", { name: "EGFR" })).toBeVisible();
  expect(within(table).getByText("II 期 81 · I 期 20")).toBeVisible();
  expect(within(landscape).queryByRole("heading", { name: "适应症" })).not.toBeInTheDocument();
  fireEvent.click(within(table).getByRole("button", { name: "筛选" }));
  expect(onSearchChange).toHaveBeenCalledWith({ ...initialFilters, targetEntityId: "target-1", offset: 0 });
});

it("saves and subscribes the complete governed pipeline query", async () => {
  renderWithQueryClient(
    <PipelineView
      {...defaultAnalysisProps}
      displayMode="landscape"
      analysisDimension="targets"
      analysisLimit={50}
      analysisStageScope="global"
      targetAggregation="primary"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  await screen.findByLabelText("管线竞争格局");
  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  const dialog = screen.getByRole("dialog", { name: "保存当前管线检索" });
  fireEvent.change(within(dialog).getByLabelText("名称"), { target: { value: "EGFR global landscape" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(savePipelineSearch).toHaveBeenCalledWith(
      {
        name: "EGFR global landscape",
        filters: initialFilters,
        analysis: {
          dimension: "targets",
          view: "chart",
          limit: 50,
          stageScope: "global",
          targetAggregation: "primary",
        },
        displayMode: "landscape",
        shared: false,
        monitor: true,
      },
      expect.any(Object),
    ),
  );
  expect(await screen.findByText("管线检索已保存并启用监控")).toBeVisible();
});

it("renders ungoverned program status detail without promoting it to a governed badge", async () => {
  vi.mocked(searchPipelines).mockResolvedValue({
    ...pipelineResult,
    items: [
      {
        ...pipelineResult.items[0],
        id: "program-ungoverned",
        status_detail: "paused pending partner decision",
        program_status: null,
      },
    ],
    total: 1,
  });
  renderWithQueryClient(
    <PipelineView
      displayMode="list"
      resultGrain="program"
      analysisDimension="all"
      analysisView="chart"
      analysisLimit={8}
      analysisStageScope="overall"
      targetAggregation="all"
      initialFilters={initialFilters}
      onSearchChange={vi.fn()}
      onDisplayModeChange={vi.fn()}
      onResultGrainChange={vi.fn()}
      onAnalysisChange={vi.fn()}
      onOpenDrug={vi.fn()}
      onOpenEntity={vi.fn()}
      onOpenTrialsForDrug={vi.fn()}
      onOpenDealsForDrug={vi.fn()}
    />,
  );

  const table = await screen.findByRole("table", { name: "药物与研发管线结果" });
  expect(within(table).getByText("状态未记录")).toBeInTheDocument();
  expect(table).not.toHaveTextContent("治理");
  expect(within(table).getByText("paused pending partner decision")).toBeInTheDocument();
  expect(within(table).queryByText("进行中")).not.toBeInTheDocument();
});
