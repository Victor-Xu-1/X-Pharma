import { contractRequest } from "../contract";
import type {
  DevelopmentPhase,
  PipelineSavedSearchQuery,
  PipelineSearchResult,
  TrialResultEvaluation,
} from "../generated";
import { MonitoringService, PipelinesService } from "../generated";
import { effectiveSort, type SortCriterion } from "./sorting";

const phases = new Set<DevelopmentPhase>([
  "discovery",
  "preclinical",
  "ind",
  "phase_1",
  "phase_1_2",
  "phase_2",
  "phase_2_3",
  "phase_3",
  "filed",
  "approved",
  "discontinued",
]);

export const pipelineSortFields = [
  "status_date",
  "drug_name",
  "target_name",
  "disease_name",
  "organization_name",
  "modality",
  "mechanism_of_action",
  "phase",
  "status_detail",
  "geography",
  "global_phase",
  "china_phase",
  "global_phase_started_at",
  "china_phase_started_at",
] as const;
export type PipelineSortField = (typeof pipelineSortFields)[number];
export type SortDirection = "asc" | "desc";

export const pipelineAnalysisDimensions = [
  "all",
  "global_phase",
  "china_phase",
  "targets",
  "target_combinations",
  "diseases",
  "organizations",
  "modality",
  "geography",
] as const;
export type PipelineAnalysisDimension = (typeof pipelineAnalysisDimensions)[number];
export type PipelineAnalysisView = "chart" | "table";
export type PipelineAnalysisLimit = 5 | 8 | 20 | 50 | 100 | 200;
export type PipelineAnalysisStageScope = "overall" | "global" | "china";
export type PipelineTargetAggregation = "all" | "primary";
export type PipelineResultGrain = "program" | "drug";
export const PIPELINE_PAGE_SIZE = 20;

export interface PipelineAnalysisOptions {
  limit: PipelineAnalysisLimit;
  stageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
}

export interface PipelineSearchFilters {
  query: string;
  modalities: string[];
  innovationTypes: string[];
  therapeuticAreas: string[];
  drugCategories: string[];
  programStatus: string;
  organizationRole: string;
  organizationType: string;
  organizationCountryRegion: string;
  phase: string;
  geography: string;
  statusDateFrom: string;
  statusDateTo: string;
  drugEntityId: string;
  targetEntityId: string;
  targetCombinationKey: string;
  diseaseEntityId: string;
  organizationEntityId: string;
  globalPhase: string;
  chinaPhase: string;
  globalPhaseStartedFrom: string;
  globalPhaseStartedTo: string;
  chinaPhaseStartedFrom: string;
  chinaPhaseStartedTo: string;
  developmentRightsRegion: string;
  commercializationRightsRegion: string;
  programTags: string[];
  milestoneType: string;
  milestoneFrom: string;
  milestoneTo: string;
  hasClinicalResults: "" | "true" | "false";
  clinicalResultEvaluation: string;
  hasDeal: "" | "true" | "false";
  dealCurrency: string;
  dealTotalPotentialAmountMin: string;
  dealTotalPotentialAmountMax: string;
  sortBy: PipelineSortField;
  sortDirection: SortDirection;
  sort?: SortCriterion<PipelineSortField>[];
  offset: number;
}

export const emptyPipelineSearchFilters = (): PipelineSearchFilters => ({
  query: "",
  modalities: [],
  innovationTypes: [],
  therapeuticAreas: [],
  drugCategories: [],
  programStatus: "",
  organizationRole: "",
  organizationType: "",
  organizationCountryRegion: "",
  phase: "",
  geography: "",
  statusDateFrom: "",
  statusDateTo: "",
  drugEntityId: "",
  targetEntityId: "",
  targetCombinationKey: "",
  diseaseEntityId: "",
  organizationEntityId: "",
  globalPhase: "",
  chinaPhase: "",
  globalPhaseStartedFrom: "",
  globalPhaseStartedTo: "",
  chinaPhaseStartedFrom: "",
  chinaPhaseStartedTo: "",
  developmentRightsRegion: "",
  commercializationRightsRegion: "",
  programTags: [],
  milestoneType: "",
  milestoneFrom: "",
  milestoneTo: "",
  hasClinicalResults: "",
  clinicalResultEvaluation: "",
  hasDeal: "",
  dealCurrency: "",
  dealTotalPotentialAmountMin: "",
  dealTotalPotentialAmountMax: "",
  sortBy: "status_date",
  sortDirection: "desc",
  sort: [{ field: "status_date", direction: "desc" }],
  offset: 0,
});

export const pipelineKeys = {
  search: (
    filters: PipelineSearchFilters,
    analysis: PipelineAnalysisOptions,
    resultGrain: PipelineResultGrain = "program",
  ) => ["intelligence", "pipelines", filters, analysis, resultGrain] as const,
  facetCatalog: () => ["intelligence", "pipelines", "facet-catalog"] as const,
};

export type PipelineFacetCatalog = Pick<PipelineSearchResult, "as_of" | "facets" | "warnings">;

export async function loadPipelineFacetCatalog(signal?: AbortSignal): Promise<PipelineFacetCatalog> {
  const result = await contractRequest(
    PipelinesService.searchPipelinesApiV1PipelinesGet({
      sort: ["status_date:desc"],
      landscapeLimit: 5,
      landscapeStageScope: "overall",
      landscapeTargetAggregation: "all",
      limit: 1,
      offset: 0,
    }),
    signal,
  );
  return { as_of: result.as_of, facets: result.facets, warnings: result.warnings };
}

export function asDevelopmentPhase(value: string): DevelopmentPhase | undefined {
  return phases.has(value as DevelopmentPhase) ? (value as DevelopmentPhase) : undefined;
}

function startOfDay(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function endOfDay(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function asOptionalBoolean(value: "" | "true" | "false"): boolean | undefined {
  return value === "" ? undefined : value === "true";
}

function asOptionalAmount(value: string): number | undefined {
  return value === "" ? undefined : Number(value);
}

export async function searchPipelines(
  filters: PipelineSearchFilters,
  analysis: PipelineAnalysisOptions,
  signal?: AbortSignal,
  resultGrain: PipelineResultGrain = "program",
): Promise<PipelineSearchResult> {
  return contractRequest(
    PipelinesService.searchPipelinesApiV1PipelinesGet({
      q: filters.query.trim() || undefined,
      modality: filters.modalities.length ? filters.modalities : undefined,
      innovationType: filters.innovationTypes.length ? filters.innovationTypes : undefined,
      therapeuticArea: filters.therapeuticAreas.length ? filters.therapeuticAreas : undefined,
      drugCategory: filters.drugCategories.length ? filters.drugCategories : undefined,
      programStatus: (filters.programStatus || undefined) as PipelineSavedSearchQuery["program_status"],
      organizationRole: (filters.organizationRole || undefined) as PipelineSavedSearchQuery["organization_role"],
      organizationType: filters.organizationType || undefined,
      organizationCountryRegion: filters.organizationCountryRegion || undefined,
      phase: asDevelopmentPhase(filters.phase),
      geography: filters.geography || undefined,
      statusDateFrom: startOfDay(filters.statusDateFrom),
      statusDateTo: endOfDay(filters.statusDateTo),
      drugEntityId: filters.drugEntityId || undefined,
      targetEntityId: filters.targetEntityId || undefined,
      targetCombinationKey: filters.targetCombinationKey || undefined,
      diseaseEntityId: filters.diseaseEntityId || undefined,
      organizationEntityId: filters.organizationEntityId || undefined,
      globalPhase: asDevelopmentPhase(filters.globalPhase),
      chinaPhase: asDevelopmentPhase(filters.chinaPhase),
      globalPhaseStartedFrom: startOfDay(filters.globalPhaseStartedFrom),
      globalPhaseStartedTo: endOfDay(filters.globalPhaseStartedTo),
      chinaPhaseStartedFrom: startOfDay(filters.chinaPhaseStartedFrom),
      chinaPhaseStartedTo: endOfDay(filters.chinaPhaseStartedTo),
      developmentRightsRegion: filters.developmentRightsRegion || undefined,
      commercializationRightsRegion: filters.commercializationRightsRegion || undefined,
      programTag: filters.programTags.length ? filters.programTags : undefined,
      milestoneType: filters.milestoneType || undefined,
      milestoneFrom: startOfDay(filters.milestoneFrom),
      milestoneTo: endOfDay(filters.milestoneTo),
      hasClinicalResults: asOptionalBoolean(filters.hasClinicalResults),
      clinicalResultEvaluation: (filters.clinicalResultEvaluation || undefined) as TrialResultEvaluation | undefined,
      hasDeal: asOptionalBoolean(filters.hasDeal),
      dealCurrency: filters.dealCurrency || undefined,
      dealTotalPotentialAmountMin: asOptionalAmount(filters.dealTotalPotentialAmountMin),
      dealTotalPotentialAmountMax: asOptionalAmount(filters.dealTotalPotentialAmountMax),
      sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      landscapeLimit: analysis.limit,
      landscapeStageScope: analysis.stageScope,
      landscapeTargetAggregation: analysis.targetAggregation,
      resultGrain,
      limit: PIPELINE_PAGE_SIZE,
      offset: filters.offset,
    }),
    signal,
  );
}

function savedPipelineQuery(
  filters: PipelineSearchFilters,
  analysis: PipelineAnalysisOptions & { dimension: PipelineAnalysisDimension; view: PipelineAnalysisView },
  displayMode: "list" | "landscape",
): PipelineSavedSearchQuery {
  return {
    q: filters.query.trim() || undefined,
    modality: filters.modalities.length ? filters.modalities : undefined,
    innovation_type: filters.innovationTypes.length ? filters.innovationTypes : undefined,
    therapeutic_area: filters.therapeuticAreas.length ? filters.therapeuticAreas : undefined,
    drug_category: filters.drugCategories.length ? filters.drugCategories : undefined,
    program_status: (filters.programStatus || undefined) as PipelineSavedSearchQuery["program_status"],
    organization_role: (filters.organizationRole || undefined) as PipelineSavedSearchQuery["organization_role"],
    organization_type: filters.organizationType || undefined,
    organization_country_region: filters.organizationCountryRegion || undefined,
    phase: asDevelopmentPhase(filters.phase),
    geography: filters.geography || undefined,
    status_date_from: filters.statusDateFrom || undefined,
    status_date_to: filters.statusDateTo || undefined,
    drug_entity_id: filters.drugEntityId || undefined,
    target_entity_id: filters.targetEntityId || undefined,
    target_combination_key: filters.targetCombinationKey || undefined,
    disease_entity_id: filters.diseaseEntityId || undefined,
    organization_entity_id: filters.organizationEntityId || undefined,
    global_phase: asDevelopmentPhase(filters.globalPhase),
    china_phase: asDevelopmentPhase(filters.chinaPhase),
    global_phase_started_from: filters.globalPhaseStartedFrom || undefined,
    global_phase_started_to: filters.globalPhaseStartedTo || undefined,
    china_phase_started_from: filters.chinaPhaseStartedFrom || undefined,
    china_phase_started_to: filters.chinaPhaseStartedTo || undefined,
    development_rights_region: filters.developmentRightsRegion || undefined,
    commercialization_rights_region: filters.commercializationRightsRegion || undefined,
    program_tag: filters.programTags.length ? filters.programTags : undefined,
    milestone_type: filters.milestoneType || undefined,
    milestone_from: filters.milestoneFrom || undefined,
    milestone_to: filters.milestoneTo || undefined,
    has_clinical_results: asOptionalBoolean(filters.hasClinicalResults),
    clinical_result_evaluation: (filters.clinicalResultEvaluation || undefined) as TrialResultEvaluation | undefined,
    has_deal: asOptionalBoolean(filters.hasDeal),
    deal_currency: filters.dealCurrency || undefined,
    deal_total_potential_amount_min: asOptionalAmount(filters.dealTotalPotentialAmountMin),
    deal_total_potential_amount_max: asOptionalAmount(filters.dealTotalPotentialAmountMax),
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
    sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: displayMode,
    analysis_dimension: analysis.dimension,
    analysis_view: analysis.view,
    analysis_limit: analysis.limit,
    analysis_stage_scope: analysis.stageScope,
    target_aggregation: analysis.targetAggregation,
  };
}

export function hasPipelineSearchFilter(filters: PipelineSearchFilters): boolean {
  return Object.entries(filters).some(
    ([key, value]) =>
      !["sortBy", "sortDirection", "sort", "offset"].includes(key) &&
      (Array.isArray(value) ? value.length > 0 : value !== "" && value !== 0),
  );
}

export async function savePipelineSearch({
  name,
  filters,
  analysis,
  displayMode,
  shared,
  monitor,
}: {
  name: string;
  filters: PipelineSearchFilters;
  analysis: PipelineAnalysisOptions & { dimension: PipelineAnalysisDimension; view: PipelineAnalysisView };
  displayMode: "list" | "landscape";
  shared: boolean;
  monitor: boolean;
}): Promise<{ message: string }> {
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query_type: "pipeline_search",
        query: savedPipelineQuery(filters, analysis, displayMode),
        visibility: shared ? "tenant" : "private",
      },
    }),
  );
  if (monitor) {
    try {
      await contractRequest(
        MonitoringService.createMonitoringTopicApiV1MonitoringTopicsPost({
          requestBody: { name: name.trim(), saved_search_id: saved.id },
        }),
      );
    } catch (error) {
      return { message: `检索已保存，但监控未启用：${error instanceof Error ? error.message : "未知错误"}` };
    }
  }
  return { message: monitor ? "管线检索已保存并启用监控" : "管线检索已保存" };
}
