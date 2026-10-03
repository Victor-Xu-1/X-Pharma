import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, BookmarkPlus, ExternalLink, List, Search } from "lucide-react";
import { type FormEvent, useCallback, useDeferredValue, useMemo, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { formatDate, ProfessionalQueryState, QueryRefreshButton, StatusBadge } from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { FacetMultiSelect } from "../components/FacetMultiSelect";
import { PipelineLandscape, type PipelineLandscapeFilterField } from "../components/PipelineLandscape";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { SecondaryFilters } from "../components/SecondaryFilters";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  emptyPipelineSearchFilters,
  hasPipelineSearchFilter,
  PIPELINE_PAGE_SIZE,
  type PipelineAnalysisDimension,
  type PipelineAnalysisLimit,
  type PipelineAnalysisStageScope,
  type PipelineAnalysisView,
  type PipelineResultGrain,
  type PipelineSearchFilters,
  type PipelineTargetAggregation,
  pipelineKeys,
  pipelineSortFields,
  savePipelineSearch,
  searchPipelines,
} from "../lib/contracts/pipeline";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import type { CompetitiveProgramRead } from "../lib/generated";
import {
  pipelineBooleanSignalLabels as booleanSignalLabels,
  pipelineResultEvaluationLabels as resultEvaluationLabels,
  validatePipelineSignalFilters,
} from "../lib/pipelineSignals";
import { programModalityLabel, programTagLabel, publicProgramTags } from "../lib/programDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import {
  IndicationLinks,
  OrganizationLinks,
  organizationRoleLabels,
  pipelineMechanisms,
  pipelineModalities,
  TargetLinks,
} from "./pipeline/ProgramCells";

const pipelineRowId = (program: CompetitiveProgramRead) => program.id;
const pipelineEntityId = (program: CompetitiveProgramRead) => program.drug_entity_id;
const defaultPipelineSorting: SortingState = [{ id: "status_date", desc: true }];
const appliedFilterLabels = {
  q: "关键词",
  modality: "药物类型",
  innovation_type: "创新类型",
  therapeutic_area: "适应症领域",
  drug_category: "药品类别",
  program_status: "项目状态",
  organization_role: "机构角色",
  organization_type: "机构类型",
  organization_country_region: "机构所在地区",
  phase: "总体最高阶段",
  geography: "记录地区",
  status_date_from: "状态日期",
  status_date_to: "状态日期",
  drug_entity_id: "药品",
  target_entity_id: "靶点",
  target_combination_key: "靶点组合",
  disease_entity_id: "适应症",
  organization_entity_id: "研发机构",
  global_phase: "全球最高阶段",
  china_phase: "中国最高阶段",
  global_phase_started_from: "全球阶段起始",
  global_phase_started_to: "全球阶段起始",
  china_phase_started_from: "中国阶段起始",
  china_phase_started_to: "中国阶段起始",
  development_rights_region: "研发权益地区",
  commercialization_rights_region: "商业化权益地区",
  program_tag: "项目标签",
  milestone_type: "里程碑类型",
  milestone_from: "里程碑日期",
  milestone_to: "里程碑日期",
  has_clinical_results: "临床结果",
  clinical_result_evaluation: "结果评价",
  has_deal: "交易记录",
  deal_currency: "交易币种",
  deal_total_potential_amount_min: "潜在总额",
  deal_total_potential_amount_max: "潜在总额",
} as const;

const phaseLabels: Record<string, string> = {
  discovery: "发现",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I 期",
  phase_1_2: "I/II 期",
  phase_2: "II 期",
  phase_2_3: "II/III 期",
  phase_3: "III 期",
  filed: "申报",
  approved: "已批准",
  discontinued: "终止",
};

const programStatusLabels: Record<string, string> = {
  active: "进行中",
  inactive: "已停止",
  unknown: "状态未披露",
};

export function PipelineView({
  displayMode,
  resultGrain,
  analysisDimension,
  analysisView,
  analysisLimit,
  analysisStageScope,
  targetAggregation,
  initialFilters,
  onSearchChange,
  onDisplayModeChange,
  onResultGrainChange,
  onAnalysisChange,
  onOpenDrug,
  onOpenEntity,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onOpenTrialsForDrug,
  onOpenDealsForDrug,
}: {
  displayMode: "list" | "landscape";
  resultGrain: PipelineResultGrain;
  analysisDimension: PipelineAnalysisDimension;
  analysisView: PipelineAnalysisView;
  analysisLimit: PipelineAnalysisLimit;
  analysisStageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
  initialFilters: PipelineSearchFilters;
  onSearchChange: (filters: PipelineSearchFilters) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onResultGrainChange: (grain: PipelineResultGrain) => void;
  onAnalysisChange: (next: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
  onOpenDrug: (entityId: string) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTarget?: (entityId: string) => void;
  onOpenDisease?: (entityId: string) => void;
  onOpenOrganization?: (entityId: string) => void;
  onOpenTrialsForDrug: (entityId: string) => void;
  onOpenDealsForDrug: (entityId: string) => void;
}) {
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [entityValueLabels, setEntityValueLabels] = useState<Record<string, Record<string, string>>>({});
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const [filterError, setFilterError] = useState("");
  const analysis = { limit: analysisLimit, stageScope: analysisStageScope, targetAggregation };
  const resultQueryKey = pipelineKeys.search(initialFilters, analysis, resultGrain);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchPipelines(initialFilters, analysis, signal, resultGrain),
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const save = useMutation({ mutationFn: savePipelineSearch });

  function updateFilter<Key extends keyof PipelineSearchFilters>(key: Key, value: PipelineSearchFilters[Key]) {
    setFilterError("");
    setFilters((current) => ({ ...current, [key]: value }));
  }

  const rememberEntity = useCallback((field: string, entityId: string, displayName?: string) => {
    if (!entityId || !displayName) return;
    setEntityValueLabels((current) => {
      if (current[field]?.[entityId] === displayName) return current;
      return { ...current, [field]: { ...current[field], [entityId]: displayName } };
    });
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    const signalError = validatePipelineSignalFilters(filters);
    if (signalError) {
      setFilterError(signalError);
      return;
    }
    setFilterError("");
    onSearchChange({ ...filters, query: filters.query.trim(), offset: 0 });
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        filters: initialFilters,
        analysis: {
          ...analysis,
          dimension: analysisDimension,
          view: analysisView,
        },
        displayMode,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome.message);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "管线检索保存失败");
    }
  }

  function clearFilters() {
    const empty = emptyPipelineSearchFilters();
    setFilters(empty);
    setEntityValueLabels({});
    setFilterError("");
    onSearchChange(empty);
  }

  function applyLandscapeFilter(field: PipelineLandscapeFilterField, value: string, label?: string) {
    if (value === "__missing__") return;
    if (field === "targetCombinationKey" && label) rememberEntity("target_combination_key", value, label);
    if (field === "modality") {
      // Modality is a multi-select condition: a landscape drill focuses on that single
      // bucket, expressed as a single-element set.
      onSearchChange({ ...initialFilters, modalities: [value], offset: 0 });
      return;
    }
    onSearchChange({ ...initialFilters, [field]: value, offset: 0 });
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "status_date", direction: "desc" });
    if (!sort.every((criterion) => pipelineSortFields.includes(criterion.field as PipelineSearchFilters["sortBy"]))) {
      return;
    }
    const normalizedSort = sort as NonNullable<PipelineSearchFilters["sort"]>;
    onSearchChange({
      ...initialFilters,
      sortBy: normalizedSort[0].field,
      sortDirection: normalizedSort[0].direction,
      sort: normalizedSort,
      offset: 0,
    });
  }

  const columns = useMemo<ColumnDef<CompetitiveProgramRead, unknown>[]>(
    () => [
      {
        accessorKey: "drug_name",
        header: "药物",
        size: 170,
        cell: ({ row }) => {
          const tags = publicProgramTags(row.original.program_tags).map(programTagLabel);
          const aggregateSummary =
            resultGrain === "drug" && row.original.project_count && row.original.project_count > 1
              ? `${row.original.project_count} 个研发项目`
              : "";
          const subtitle = [...tags, aggregateSummary].filter(Boolean).join(" · ");
          return (
            <button
              className="entity-name-button"
              type="button"
              onClick={() => onOpenDrug(row.original.drug_entity_id)}
            >
              <strong>{row.original.drug_name}</strong>
              {subtitle ? <small className="cell-subtitle">{subtitle}</small> : null}
            </button>
          );
        },
      },
      {
        accessorKey: "target_name",
        header: "靶点组合",
        size: 180,
        cell: ({ row }) => <TargetLinks program={row.original} onOpen={openTarget} />,
      },
      {
        accessorKey: "disease_name",
        header: "适应症",
        size: 180,
        cell: ({ row }) => <IndicationLinks program={row.original} onOpen={openDisease} />,
      },
      {
        accessorKey: "organization_name",
        header: "参与机构与角色",
        size: 210,
        cell: ({ row }) => <OrganizationLinks program={row.original} onOpen={openOrganization} />,
      },
      {
        accessorKey: "modality",
        header: "药物类型",
        size: 125,
        cell: ({ row }) => pipelineModalities(row.original),
      },
      {
        accessorKey: "mechanism_of_action",
        header: "作用机制",
        size: 180,
        cell: ({ row }) => pipelineMechanisms(row.original),
      },
      {
        accessorKey: "phase",
        header: "总体阶段",
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? <StatusBadge value={phaseLabels[value] ?? value} /> : <span>未披露</span>;
        },
      },
      {
        accessorKey: "status_detail",
        header: "项目状态",
        size: 130,
        cell: ({ row }) => {
          // The badge only ever shows the governed vocabulary; ungoverned source text is
          // kept visible as detail instead of being rendered as if it were a known state.
          const governed = row.original.program_status;
          const detail = row.original.status_detail;
          if (!governed && !detail) return <span>未披露</span>;
          return (
            <span className="domain-primary-cell">
              {governed ? <StatusBadge value={programStatusLabels[governed]} /> : <span>状态未记录</span>}
              {detail && detail !== governed ? <small className="cell-subtitle">{detail}</small> : null}
            </span>
          );
        },
      },
      {
        accessorKey: "geography",
        header: "记录地区",
        size: 115,
        cell: ({ getValue }) => String(getValue() ?? "未披露"),
      },
      {
        accessorKey: "global_phase",
        header: "全球阶段",
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? <StatusBadge value={phaseLabels[value] ?? value} /> : <span>未披露</span>;
        },
      },
      {
        accessorKey: "global_phase_started_at",
        header: "全球阶段起始",
        size: 130,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "china_phase",
        header: "中国阶段",
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? <StatusBadge value={phaseLabels[value] ?? value} /> : <span>未披露</span>;
        },
      },
      {
        accessorKey: "china_phase_started_at",
        header: "中国阶段起始",
        size: 130,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "clinical_signals",
        header: "临床信号",
        size: 150,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-stacked-copy">
            {(row.original.clinical_trial_count ?? 0) > 0 ? (
              <button
                className="table-link-button"
                type="button"
                aria-label={`查看 ${row.original.drug_name} 的 ${row.original.clinical_trial_count} 项临床试验`}
                onClick={() => onOpenTrialsForDrug(row.original.drug_entity_id)}
              >
                {row.original.clinical_trial_count} 项试验
              </button>
            ) : (
              <span>0 项试验</span>
            )}
            <small>
              {row.original.has_clinical_results
                ? (row.original.clinical_result_evaluations ?? [])
                    .map((value) => resultEvaluationLabels[value] ?? value)
                    .join("、") || "已有结果"
                : "未观察到结果"}
            </small>
          </span>
        ),
      },
      {
        id: "deal_signals",
        header: "交易信号",
        size: 135,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-stacked-copy">
            {(row.original.deal_count ?? 0) > 0 ? (
              <button
                className="table-link-button"
                type="button"
                aria-label={`查看 ${row.original.drug_name} 的 ${row.original.deal_count} 笔交易`}
                onClick={() => onOpenDealsForDrug(row.original.drug_entity_id)}
              >
                {row.original.deal_count} 笔交易
              </button>
            ) : (
              <span>0 笔交易</span>
            )}
            <small>{row.original.deal_currencies?.join("、") || "未披露币种"}</small>
          </span>
        ),
      },
      {
        id: "rights",
        header: "权益地区",
        size: 190,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-stacked-copy">
            <span>研发：{row.original.development_rights_regions?.join("、") || "未披露"}</span>
            <small>商业化：{row.original.commercialization_rights_regions?.join("、") || "未披露"}</small>
          </span>
        ),
      },
      {
        id: "latest_milestone",
        header: "最新里程碑",
        size: 180,
        enableSorting: false,
        cell: ({ row }) => {
          const milestone = row.original.milestones?.at(-1);
          return milestone ? (
            <span className="table-stacked-copy">
              <span>{milestone.title}</span>
              <small>{formatDate(milestone.occurred_at)}</small>
            </span>
          ) : (
            <span>未披露</span>
          );
        },
      },
      {
        accessorKey: "status_date",
        header: "状态日期",
        size: 120,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "traceability",
        header: "来源",
        size: 86,
        enableSorting: false,
        cell: ({ row }) => (row.original.source_document_id ? <StatusBadge value="可追溯" /> : <span>待补充</span>),
      },
      {
        id: "open",
        header: "档案",
        size: 60,
        enableSorting: false,
        cell: ({ row }) => (
          <button
            className="icon-button"
            type="button"
            title={`打开 ${row.original.drug_name} 档案`}
            aria-label={`打开 ${row.original.drug_name} 档案`}
            onClick={() => onOpenDrug(row.original.drug_entity_id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onOpenDealsForDrug, onOpenDrug, openOrganization, openTarget, openDisease, onOpenTrialsForDrug, resultGrain],
  );

  // Keep the filter surface responsive while a large real result page is reconciled.
  // The query remains authoritative; only its React presentation is deferred.
  const data = useDeferredValue(result.data);
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    pipelineRowId,
    pipelineEntityId,
  );
  const modalities = facetOptions(data?.facets, "modality", filters.modalities);
  const innovationTypes = facetOptions(data?.facets, "innovation_type", filters.innovationTypes);
  const therapeuticAreas = facetOptions(data?.facets, "therapeutic_area", filters.therapeuticAreas);
  const drugCategories = facetOptions(data?.facets, "drug_category", filters.drugCategories);
  const phases = facetOptions(data?.facets, "phase", filters.phase);
  const geographies = facetOptions(data?.facets, "geography", filters.geography);
  const globalPhases = facetOptions(data?.facets, "global_phase", filters.globalPhase);
  const chinaPhases = facetOptions(data?.facets, "china_phase", filters.chinaPhase);
  const developmentRights = facetOptions(data?.facets, "development_rights_region", filters.developmentRightsRegion);
  const commercializationRights = facetOptions(
    data?.facets,
    "commercialization_rights_region",
    filters.commercializationRightsRegion,
  );
  const programTags = publicProgramTags(facetOptions(data?.facets, "program_tag", filters.programTags));
  const milestoneTypes = facetOptions(data?.facets, "milestone_type", filters.milestoneType);
  const resultEvaluations = Object.keys(resultEvaluationLabels);
  const dealCurrencies = facetOptions(data?.facets, "deal_currency", filters.dealCurrency);
  const organizationTypes = facetOptions(data?.facets, "organization_type", filters.organizationType);
  const organizationCountries = facetOptions(
    data?.facets,
    "organization_country_region",
    filters.organizationCountryRegion,
  );
  const hasFilters = Object.entries(initialFilters).some(
    ([key, value]) =>
      !["offset", "sortBy", "sortDirection", "sort"].includes(key) &&
      (Array.isArray(value) ? value.length > 0 : Boolean(value)),
  );
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }
  const advancedCount = [
    filters.globalPhase,
    filters.organizationRole,
    filters.organizationType,
    filters.organizationCountryRegion,
    filters.chinaPhase,
    filters.globalPhaseStartedFrom,
    filters.globalPhaseStartedTo,
    filters.chinaPhaseStartedFrom,
    filters.chinaPhaseStartedTo,
    filters.developmentRightsRegion,
    filters.commercializationRightsRegion,
    filters.programTags.length,
    filters.milestoneType,
    filters.milestoneFrom,
    filters.milestoneTo,
    filters.statusDateFrom,
    filters.statusDateTo,
  ].filter(Boolean).length;
  const signalCount = [
    filters.hasClinicalResults,
    filters.clinicalResultEvaluation,
    filters.hasDeal,
    filters.dealCurrency,
    filters.dealTotalPotentialAmountMin,
    filters.dealTotalPotentialAmountMax,
  ].filter(Boolean).length;
  const entityValueMap = {
    modality: Object.fromEntries(modalities.map((value) => [value, programModalityLabel(value)])),
    drug_entity_id: entityValueLabels.drug_entity_id ?? {},
    target_entity_id: entityValueLabels.target_entity_id ?? {},
    target_combination_key: entityValueLabels.target_combination_key ?? {},
    disease_entity_id: entityValueLabels.disease_entity_id ?? {},
    organization_entity_id: entityValueLabels.organization_entity_id ?? {},
    organization_role: organizationRoleLabels,
    phase: phaseLabels,
    global_phase: phaseLabels,
    china_phase: phaseLabels,
    has_clinical_results: booleanSignalLabels,
    clinical_result_evaluation: resultEvaluationLabels,
    has_deal: booleanSignalLabels,
  };

  return (
    <section className="data-section pipeline-section">
      <div className="explorer-intro">
        <p>按药品、靶点、适应症、研发机构、全球与中国阶段、权益地区及里程碑组合查询。</p>
      </div>

      <form className="domain-filter-bar pipeline-filter-bar" onSubmit={submit} aria-label="药物与管线筛选">
        <div className="pipeline-primary-filters">
          <label className="domain-query-field">
            <span>关键词</span>
            <span className="input-with-icon">
              <Search size={16} />
              <input
                value={filters.query}
                onChange={(event) => updateFilter("query", event.target.value)}
                placeholder="药物、作用机制或项目名称"
                maxLength={500}
              />
            </span>
          </label>
          <FacetMultiSelect
            label="药物类型"
            options={modalities.map((value) => ({
              value,
              label: programModalityLabel(value),
              count: data?.facets?.modality?.[value] ?? 0,
            }))}
            selected={filters.modalities}
            onChange={(values) => updateFilter("modalities", values)}
          />
          <label>
            <span>项目状态</span>
            <select
              value={filters.programStatus}
              onChange={(event) => updateFilter("programStatus", event.target.value)}
            >
              <option value="">全部</option>
              {(["active", "inactive", "unknown"] as const).map((value) => (
                <option
                  value={value}
                  key={value}
                  disabled={
                    !filters.programStatus || filters.programStatus !== value
                      ? (data?.facets?.program_status?.[value] ?? 0) === 0
                      : false
                  }
                >
                  {programStatusLabels[value]} ({data?.facets?.program_status?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>总体最高阶段</span>
            <select value={filters.phase} onChange={(event) => updateFilter("phase", event.target.value)}>
              <option value="">全部</option>
              {phases.map((value) => (
                <option value={value} key={value}>
                  {phaseLabels[value] ?? value} ({data?.facets?.phase?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
        </div>

        <fieldset className="pipeline-entity-filters" aria-label="药品、靶点、适应症与研发机构">
          <EntityFilterSelect
            label="药品"
            entityType="drug"
            value={filters.drugEntityId}
            placeholder="输入规范药品"
            onChange={(entityId, name) => {
              updateFilter("drugEntityId", entityId);
              rememberEntity("drug_entity_id", entityId, name);
            }}
            onResolved={(entityId, name) => rememberEntity("drug_entity_id", entityId, name)}
          />
          <EntityFilterSelect
            label="靶点"
            entityType="target"
            value={filters.targetEntityId}
            placeholder="输入至少 2 个字符"
            onChange={(entityId, name) => {
              updateFilter("targetEntityId", entityId);
              rememberEntity("target_entity_id", entityId, name);
            }}
            onResolved={(entityId, name) => rememberEntity("target_entity_id", entityId, name)}
          />
          <EntityFilterSelect
            label="适应症"
            entityType="disease"
            value={filters.diseaseEntityId}
            placeholder="输入疾病或适应症"
            onChange={(entityId, name) => {
              updateFilter("diseaseEntityId", entityId);
              rememberEntity("disease_entity_id", entityId, name);
            }}
            onResolved={(entityId, name) => rememberEntity("disease_entity_id", entityId, name)}
          />
          <EntityFilterSelect
            label="研发机构"
            entityType="organization"
            value={filters.organizationEntityId}
            placeholder="输入机构名称"
            onChange={(entityId, name) => {
              updateFilter("organizationEntityId", entityId);
              rememberEntity("organization_entity_id", entityId, name);
            }}
            onResolved={(entityId, name) => rememberEntity("organization_entity_id", entityId, name)}
          />
        </fieldset>

        <SecondaryFilters
          label="药物分类与记录地区"
          activeCount={
            [
              filters.innovationTypes.length,
              filters.therapeuticAreas.length,
              filters.drugCategories.length,
              filters.geography,
            ].filter(Boolean).length
          }
        >
          <FacetMultiSelect
            label="创新类型"
            options={innovationTypes.map((value) => ({
              value,
              label: value,
              count: data?.facets?.innovation_type?.[value] ?? 0,
            }))}
            selected={filters.innovationTypes}
            onChange={(values) => updateFilter("innovationTypes", values)}
          />
          <FacetMultiSelect
            label="适应症领域"
            options={therapeuticAreas.map((value) => ({
              value,
              label: value,
              count: data?.facets?.therapeutic_area?.[value] ?? 0,
            }))}
            selected={filters.therapeuticAreas}
            onChange={(values) => updateFilter("therapeuticAreas", values)}
          />
          <FacetMultiSelect
            label="药品类别"
            options={drugCategories.map((value) => ({
              value,
              label: value,
              count: data?.facets?.drug_category?.[value] ?? 0,
            }))}
            selected={filters.drugCategories}
            onChange={(values) => updateFilter("drugCategories", values)}
          />
          <label>
            <span>记录地区</span>
            <select value={filters.geography} onChange={(event) => updateFilter("geography", event.target.value)}>
              <option value="">全部</option>
              {geographies.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.geography?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
        </SecondaryFilters>

        <details className="advanced-filter-panel pipeline-advanced-filters" open={advancedCount > 0 || undefined}>
          <summary>
            机构、区域阶段、权益与里程碑
            <span>{advancedCount ? `已选 ${advancedCount} 项` : "按需展开"}</span>
          </summary>
          <div className="pipeline-advanced-grid">
            <label>
              <span>机构角色</span>
              <select
                value={filters.organizationRole}
                onChange={(event) => updateFilter("organizationRole", event.target.value)}
              >
                <option value="">全部</option>
                {Object.entries(organizationRoleLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label} ({data?.facets?.organization_role?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>机构类型</span>
              <select
                value={filters.organizationType}
                onChange={(event) => updateFilter("organizationType", event.target.value)}
              >
                <option value="">全部</option>
                {organizationTypes.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.organization_type?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>机构所在地区</span>
              <select
                value={filters.organizationCountryRegion}
                onChange={(event) => updateFilter("organizationCountryRegion", event.target.value)}
              >
                <option value="">全部</option>
                {organizationCountries.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.organization_country_region?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>全球最高阶段</span>
              <select value={filters.globalPhase} onChange={(event) => updateFilter("globalPhase", event.target.value)}>
                <option value="">全部</option>
                {globalPhases.map((value) => (
                  <option value={value} key={value}>
                    {phaseLabels[value] ?? value} ({data?.facets?.global_phase?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>中国最高阶段</span>
              <select value={filters.chinaPhase} onChange={(event) => updateFilter("chinaPhase", event.target.value)}>
                <option value="">全部</option>
                {chinaPhases.map((value) => (
                  <option value={value} key={value}>
                    {phaseLabels[value] ?? value} ({data?.facets?.china_phase?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>研发权益地区</span>
              <select
                value={filters.developmentRightsRegion}
                onChange={(event) => updateFilter("developmentRightsRegion", event.target.value)}
              >
                <option value="">全部</option>
                {developmentRights.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.development_rights_region?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>商业化权益地区</span>
              <select
                value={filters.commercializationRightsRegion}
                onChange={(event) => updateFilter("commercializationRightsRegion", event.target.value)}
              >
                <option value="">全部</option>
                {commercializationRights.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.commercialization_rights_region?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            {programTags.length || filters.programTags.length ? (
              <FacetMultiSelect
                label="项目标签"
                options={programTags.map((value) => ({
                  value,
                  label: programTagLabel(value),
                  count: data?.facets?.program_tag?.[value] ?? 0,
                }))}
                selected={filters.programTags}
                onChange={(values) => updateFilter("programTags", values)}
              />
            ) : null}
            <label>
              <span>里程碑类型</span>
              <select
                value={filters.milestoneType}
                onChange={(event) => updateFilter("milestoneType", event.target.value)}
              >
                <option value="">全部</option>
                {milestoneTypes.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.milestone_type?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="date-range-fieldset">
              <legend>全球阶段起始日期</legend>
              <label>
                <span>起</span>
                <input
                  type="date"
                  value={filters.globalPhaseStartedFrom}
                  max={filters.globalPhaseStartedTo || undefined}
                  onChange={(event) => updateFilter("globalPhaseStartedFrom", event.target.value)}
                />
              </label>
              <label>
                <span>止</span>
                <input
                  type="date"
                  value={filters.globalPhaseStartedTo}
                  min={filters.globalPhaseStartedFrom || undefined}
                  onChange={(event) => updateFilter("globalPhaseStartedTo", event.target.value)}
                />
              </label>
            </fieldset>
            <fieldset className="date-range-fieldset">
              <legend>中国阶段起始日期</legend>
              <label>
                <span>起</span>
                <input
                  type="date"
                  value={filters.chinaPhaseStartedFrom}
                  max={filters.chinaPhaseStartedTo || undefined}
                  onChange={(event) => updateFilter("chinaPhaseStartedFrom", event.target.value)}
                />
              </label>
              <label>
                <span>止</span>
                <input
                  type="date"
                  value={filters.chinaPhaseStartedTo}
                  min={filters.chinaPhaseStartedFrom || undefined}
                  onChange={(event) => updateFilter("chinaPhaseStartedTo", event.target.value)}
                />
              </label>
            </fieldset>
            <fieldset className="date-range-fieldset">
              <legend>里程碑日期</legend>
              <label>
                <span>起</span>
                <input
                  type="date"
                  value={filters.milestoneFrom}
                  max={filters.milestoneTo || undefined}
                  onChange={(event) => updateFilter("milestoneFrom", event.target.value)}
                />
              </label>
              <label>
                <span>止</span>
                <input
                  type="date"
                  value={filters.milestoneTo}
                  min={filters.milestoneFrom || undefined}
                  onChange={(event) => updateFilter("milestoneTo", event.target.value)}
                />
              </label>
            </fieldset>
            <fieldset className="date-range-fieldset">
              <legend>状态更新日期</legend>
              <label>
                <span>起</span>
                <input
                  type="date"
                  value={filters.statusDateFrom}
                  max={filters.statusDateTo || undefined}
                  onChange={(event) => updateFilter("statusDateFrom", event.target.value)}
                />
              </label>
              <label>
                <span>止</span>
                <input
                  type="date"
                  value={filters.statusDateTo}
                  min={filters.statusDateFrom || undefined}
                  onChange={(event) => updateFilter("statusDateTo", event.target.value)}
                />
              </label>
            </fieldset>
          </div>
        </details>

        <details className="advanced-filter-panel pipeline-advanced-filters" open={signalCount > 0 || undefined}>
          <summary>
            临床结果与交易信号
            <span>{signalCount ? `已选 ${signalCount} 项` : "按需展开"}</span>
          </summary>
          <div className="pipeline-advanced-grid pipeline-signal-grid">
            <label>
              <span>是否已有临床结果</span>
              <select
                value={filters.hasClinicalResults}
                onChange={(event) => {
                  const value = event.target.value as PipelineSearchFilters["hasClinicalResults"];
                  setFilters((current) => ({
                    ...current,
                    hasClinicalResults: value,
                    clinicalResultEvaluation: value === "false" ? "" : current.clinicalResultEvaluation,
                  }));
                  setFilterError("");
                }}
              >
                <option value="">全部</option>
                <option value="true">有结果 ({data?.facets?.has_clinical_results?.true ?? 0})</option>
                <option value="false">无结果 ({data?.facets?.has_clinical_results?.false ?? 0})</option>
              </select>
            </label>
            <label>
              <span>临床结果评价</span>
              <select
                value={filters.clinicalResultEvaluation}
                disabled={filters.hasClinicalResults === "false"}
                onChange={(event) => updateFilter("clinicalResultEvaluation", event.target.value)}
              >
                <option value="">全部</option>
                {resultEvaluations.map((value) => (
                  <option value={value} key={value}>
                    {resultEvaluationLabels[value]} ({data?.facets?.clinical_result_evaluation?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>是否存在交易记录</span>
              <select
                value={filters.hasDeal}
                onChange={(event) => {
                  const value = event.target.value as PipelineSearchFilters["hasDeal"];
                  setFilters((current) => ({
                    ...current,
                    hasDeal: value,
                    dealCurrency: value === "false" ? "" : current.dealCurrency,
                    dealTotalPotentialAmountMin: value === "false" ? "" : current.dealTotalPotentialAmountMin,
                    dealTotalPotentialAmountMax: value === "false" ? "" : current.dealTotalPotentialAmountMax,
                  }));
                  setFilterError("");
                }}
              >
                <option value="">全部</option>
                <option value="true">有交易 ({data?.facets?.has_deal?.true ?? 0})</option>
                <option value="false">无交易 ({data?.facets?.has_deal?.false ?? 0})</option>
              </select>
            </label>
            <label>
              <span>交易币种</span>
              <select
                value={filters.dealCurrency}
                disabled={filters.hasDeal === "false"}
                onChange={(event) => updateFilter("dealCurrency", event.target.value)}
              >
                <option value="">全部</option>
                {dealCurrencies.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.deal_currency?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>潜在总额下限</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                disabled={filters.hasDeal === "false"}
                value={filters.dealTotalPotentialAmountMin}
                onChange={(event) => updateFilter("dealTotalPotentialAmountMin", event.target.value)}
                placeholder="例如 100000000"
              />
            </label>
            <label>
              <span>潜在总额上限</span>
              <input
                type="number"
                min={filters.dealTotalPotentialAmountMin || "0"}
                step="0.01"
                inputMode="decimal"
                disabled={filters.hasDeal === "false"}
                value={filters.dealTotalPotentialAmountMax}
                onChange={(event) => updateFilter("dealTotalPotentialAmountMax", event.target.value)}
                placeholder="例如 500000000"
              />
            </label>
          </div>
        </details>

        {filterError ? (
          <p className="form-error pipeline-filter-error" role="alert">
            {filterError}
          </p>
        ) : null}

        <div className="domain-filter-actions pipeline-filter-actions">
          <button className="primary-button" type="submit" disabled={result.isFetching}>
            <Search size={16} />
            查询
          </button>
          <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
            清除
          </button>
        </div>
      </form>

      <AppliedFiltersBar
        filters={data?.applied_filters}
        labels={appliedFilterLabels}
        valueLabels={entityValueMap}
        onClear={clearFilters}
      />

      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel="正在查询研发管线"
        fallbackError="管线查询失败"
        onCancel={queryCancellation.cancel}
        onRetry={retryResult}
        onDismissCancellation={queryCancellation.reset}
      >
        {data ? (
          <div className="domain-results">
            <div className="pipeline-result-toolbar">
              <QueryResultSummary
                total={data.total}
                offset={data.offset}
                count={data.items.length}
                unit={resultGrain === "drug" ? "个药物" : "条研发项目"}
                queriedAt={data.as_of}
                showRange={displayMode === "list"}
                note={
                  resultGrain === "drug" && data.project_total !== undefined
                    ? `覆盖 ${data.project_total} 条研发项目`
                    : undefined
                }
              />
              <div className="pipeline-result-actions">
                <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                <fieldset className="segmented-control">
                  <legend className="sr-only">管线结果统计粒度</legend>
                  <button
                    type="button"
                    aria-pressed={resultGrain === "drug"}
                    onClick={() => onResultGrainChange("drug")}
                  >
                    按药物
                  </button>
                  <button
                    type="button"
                    aria-pressed={resultGrain === "program"}
                    onClick={() => onResultGrainChange("program")}
                  >
                    按项目
                  </button>
                </fieldset>
                <fieldset className="segmented-control">
                  <legend className="sr-only">管线结果展示方式</legend>
                  <button
                    type="button"
                    aria-pressed={displayMode === "list"}
                    onClick={() => onDisplayModeChange("list")}
                  >
                    <List size={15} />
                    列表
                  </button>
                  <button
                    type="button"
                    aria-pressed={displayMode === "landscape"}
                    onClick={() => onDisplayModeChange("landscape")}
                  >
                    <BarChart3 size={15} />
                    格局
                  </button>
                </fieldset>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!hasPipelineSearchFilter(initialFilters)}
                  title={hasPipelineSearchFilter(initialFilters) ? "保存或订阅当前管线查询" : "至少应用一个查询条件"}
                  onClick={() => {
                    setSaveName(initialFilters.query.trim() || "管线情报监控");
                    setSaveMessage("");
                    setSaveOpen(true);
                  }}
                >
                  <BookmarkPlus size={15} />
                  保存/订阅
                </button>
                <DomainExportControl dataset="pipelines" totalRows={data.total} />
              </div>
            </div>
            {data.total && displayMode === "landscape" ? (
              <PipelineLandscape
                landscape={data.landscape}
                dimension={analysisDimension}
                view={analysisView}
                limit={analysisLimit}
                stageScope={analysisStageScope}
                targetAggregation={targetAggregation}
                onFilter={applyLandscapeFilter}
                onOpenEntity={onOpenEntity}
                onOpenTarget={openTarget}
                onOpenDisease={openDisease}
                onOpenOrganization={openOrganization}
                onAnalysisChange={onAnalysisChange}
              />
            ) : data.items.length ? (
              <VirtualDataTable
                ariaLabel="药物与研发管线结果"
                columns={columns}
                data={data.items}
                getRowId={(program) => program.id}
                preferenceKey="pipeline"
                totalRows={data.total}
                sorting={sorting}
                defaultSorting={defaultPipelineSorting}
                onSortingChange={changeSorting}
                sortingScope="all"
                toolbarActions={
                  <AddToComparisonControl
                    selectedEntityIds={selectedEntityIds}
                    onAdded={(message) => {
                      setSaveMessage(message);
                      clearSelection();
                    }}
                  />
                }
                rowSelection={{
                  selectedRowIds,
                  onChange: onSelectionChange,
                  getRowLabel: (program) => `对比 ${program.drug_name}`,
                  label: "选择对比药物",
                  maxSelectedRows: 20,
                }}
              />
            ) : (
              <EmptyQueryResult
                domain="管线数据"
                filtered={Boolean(data.applied_filters?.length)}
                onClear={clearFilters}
              />
            )}
            {displayMode === "list" ? (
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PIPELINE_PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange({ ...initialFilters, offset })}
                ariaLabel="药物管线结果分页"
              />
            ) : (
              <footer className="pipeline-landscape-footer">
                <span>{publicCoverageNotice(data.warnings)}</span>
              </footer>
            )}
          </div>
        ) : null}
      </ProfessionalQueryState>
      {saveMessage ? (
        <p className="inline-feedback" role="status">
          {saveMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel="管线"
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        onNameChange={setSaveName}
        onSharedChange={setSaveShared}
        onMonitorChange={setSaveMonitor}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void submitSavedSearch(event)}
      />
    </section>
  );
}
