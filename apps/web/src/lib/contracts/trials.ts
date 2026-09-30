import { contractRequest } from "../contract";
import type {
  ClinicalTrialDetailRead,
  ClinicalTrialSavedSearchQuery,
  ClinicalTrialSearchResult,
  DevelopmentPhase,
  TrialEntityRole,
  TrialResultEvaluation,
} from "../generated";
import { MonitoringService, TrialsService } from "../generated";
import { effectiveSort, type SortCriterion } from "./sorting";

export const trialSortFields = [
  "last_update_posted",
  "registry_id",
  "has_results",
  "result_evaluation",
  "overall_status",
  "enrollment",
  "study_type",
  "acronym",
  "initiation_type",
] as const;
export type TrialSortField = (typeof trialSortFields)[number];
export type SortDirection = "asc" | "desc";
type TrialInitiationType = NonNullable<ClinicalTrialSavedSearchQuery["initiation_type"]>;
type TrialTherapyLine = NonNullable<ClinicalTrialSavedSearchQuery["therapy_line"]>;

export interface TrialSavedSearchInput {
  query: string;
  registry: string;
  status: string;
  phase: string;
  studyType: string;
  acronym: string;
  initiationType: string;
  therapyLine: string;
  hasResults: string;
  resultEvaluation: string;
  resultsPostedFrom: string;
  resultsPostedTo: string;
  investigationalDrug: string;
  combinationDrug: string;
  investigationalTarget: string;
  combinationTarget: string;
  investigationalDrugEntityIds: string[];
  combinationDrugEntityIds: string[];
  investigationalTargetEntityIds: string[];
  combinationTargetEntityIds: string[];
  linkedDrugModalities: string[];
  linkedDrugInnovationTypes: string[];
  linkedDrugCategories: string[];
  linkedDrugProgramTags: string[];
  linkedDrugGlobalPhase: string;
  linkedDrugOrganizationCountryRegion: string;
  roleEntityId: string;
  roleEntityIds: string[];
  roleEntityRole: string;
  hasKeyResult: string;
  publicationId: string;
  conference: string;
  disclosedFrom: string;
  disclosedTo: string;
  sortBy: TrialSortField;
  sortDirection: SortDirection;
  sort?: SortCriterion<TrialSortField>[];
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
}

export const trialKeys = {
  search: (
    query: string,
    registry: string,
    status: string,
    phase: string,
    studyType: string,
    acronym: string,
    initiationType: string,
    therapyLine: string,
    hasResults: string,
    resultEvaluation: string,
    resultsPostedFrom: string,
    resultsPostedTo: string,
    investigationalDrug: string,
    combinationDrug: string,
    investigationalTarget: string,
    combinationTarget: string,
    investigationalDrugEntityIds: string[],
    combinationDrugEntityIds: string[],
    investigationalTargetEntityIds: string[],
    combinationTargetEntityIds: string[],
    linkedDrugModalities: string[],
    linkedDrugInnovationTypes: string[],
    linkedDrugCategories: string[],
    linkedDrugProgramTags: string[],
    linkedDrugGlobalPhase: string,
    linkedDrugOrganizationCountryRegion: string,
    roleEntityId: string,
    roleEntityIds: string[],
    roleEntityRole: string,
    hasKeyResult: string,
    publicationId: string,
    conference: string,
    disclosedFrom: string,
    disclosedTo: string,
    sortBy: TrialSortField,
    sortDirection: SortDirection,
    offset: number,
    sort?: readonly SortCriterion<TrialSortField>[],
  ) =>
    [
      "intelligence",
      "trials",
      {
        query,
        registry,
        status,
        phase,
        studyType,
        acronym,
        initiationType,
        therapyLine,
        hasResults,
        resultEvaluation,
        resultsPostedFrom,
        resultsPostedTo,
        investigationalDrug,
        combinationDrug,
        investigationalTarget,
        combinationTarget,
        investigationalDrugEntityIds,
        combinationDrugEntityIds,
        investigationalTargetEntityIds,
        combinationTargetEntityIds,
        linkedDrugModalities,
        linkedDrugInnovationTypes,
        linkedDrugCategories,
        linkedDrugProgramTags,
        linkedDrugGlobalPhase,
        linkedDrugOrganizationCountryRegion,
        roleEntityId,
        roleEntityIds,
        roleEntityRole,
        hasKeyResult,
        publicationId,
        conference,
        disclosedFrom,
        disclosedTo,
        sortBy,
        sortDirection,
        offset,
        sort,
      },
    ] as const,
  detail: (trialId: string) => ["intelligence", "trials", "detail", trialId] as const,
};

const resultEvaluations = new Set<TrialResultEvaluation>([
  "unfavorable",
  "not_superior",
  "non_inferior",
  "similar",
  "positive",
  "superior",
  "terminated",
]);

function asTrialResultEvaluation(value: string): TrialResultEvaluation | undefined {
  return resultEvaluations.has(value as TrialResultEvaluation) ? (value as TrialResultEvaluation) : undefined;
}

const trialEntityRoles = new Set<TrialEntityRole>([
  "investigational_drug",
  "combination_drug",
  "investigational_target",
  "combination_target",
]);

const trialInitiationTypes = new Set<TrialInitiationType>(["iit", "ist"]);
const trialTherapyLines = new Set<TrialTherapyLine>([
  "first_line",
  "second_line",
  "third_or_later",
  "prevention",
  "treatment_naive",
  "add_on",
  "adjuvant",
  "neoadjuvant",
  "maintenance",
  "consolidation",
  "induction",
  "conversion",
]);
const developmentPhases = new Set<DevelopmentPhase>([
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

function asTrialEntityRole(value: string): TrialEntityRole | undefined {
  return trialEntityRoles.has(value as TrialEntityRole) ? (value as TrialEntityRole) : undefined;
}

function asTrialInitiationType(value: string): TrialInitiationType | undefined {
  return trialInitiationTypes.has(value as TrialInitiationType) ? (value as TrialInitiationType) : undefined;
}

function asTrialTherapyLine(value: string): TrialTherapyLine | undefined {
  return trialTherapyLines.has(value as TrialTherapyLine) ? (value as TrialTherapyLine) : undefined;
}

function asDevelopmentPhase(value: string): DevelopmentPhase | undefined {
  return developmentPhases.has(value as DevelopmentPhase) ? (value as DevelopmentPhase) : undefined;
}

function optionalBoolean(value: string): boolean | undefined {
  return value === "true" ? true : value === "false" ? false : undefined;
}

function savedClinicalTrialQuery(input: TrialSavedSearchInput): ClinicalTrialSavedSearchQuery {
  const roleEntityIds = [...new Set(input.roleEntityIds)].sort();
  return {
    q: input.query.trim() || undefined,
    registry: input.registry || undefined,
    status: input.status || undefined,
    phase: input.phase || undefined,
    study_type: input.studyType || undefined,
    acronym: input.acronym.trim() || undefined,
    initiation_type: asTrialInitiationType(input.initiationType),
    therapy_line: asTrialTherapyLine(input.therapyLine),
    has_results: optionalBoolean(input.hasResults),
    result_evaluation: asTrialResultEvaluation(input.resultEvaluation),
    results_posted_from: input.resultsPostedFrom || undefined,
    results_posted_to: input.resultsPostedTo || undefined,
    investigational_drug: input.investigationalDrug.trim() || undefined,
    combination_drug: input.combinationDrug.trim() || undefined,
    investigational_target: input.investigationalTarget.trim() || undefined,
    combination_target: input.combinationTarget.trim() || undefined,
    investigational_drug_entity_ids: input.investigationalDrugEntityIds.length
      ? [...new Set(input.investigationalDrugEntityIds)].sort()
      : undefined,
    combination_drug_entity_ids: input.combinationDrugEntityIds.length
      ? [...new Set(input.combinationDrugEntityIds)].sort()
      : undefined,
    investigational_target_entity_ids: input.investigationalTargetEntityIds.length
      ? [...new Set(input.investigationalTargetEntityIds)].sort()
      : undefined,
    combination_target_entity_ids: input.combinationTargetEntityIds.length
      ? [...new Set(input.combinationTargetEntityIds)].sort()
      : undefined,
    linked_drug_modality: input.linkedDrugModalities.length
      ? [...new Set(input.linkedDrugModalities)].sort()
      : undefined,
    linked_drug_innovation_type: input.linkedDrugInnovationTypes.length
      ? [...new Set(input.linkedDrugInnovationTypes)].sort()
      : undefined,
    linked_drug_category: input.linkedDrugCategories.length
      ? [...new Set(input.linkedDrugCategories)].sort()
      : undefined,
    linked_drug_program_tag: input.linkedDrugProgramTags.length
      ? [...new Set(input.linkedDrugProgramTags)].sort()
      : undefined,
    linked_drug_global_phase: asDevelopmentPhase(input.linkedDrugGlobalPhase),
    linked_drug_organization_country_region: input.linkedDrugOrganizationCountryRegion.trim() || undefined,
    role_entity_id: roleEntityIds.length ? undefined : input.roleEntityId || undefined,
    role_entity_ids: roleEntityIds.length ? roleEntityIds : undefined,
    role_entity_role: roleEntityIds.length || input.roleEntityId ? asTrialEntityRole(input.roleEntityRole) : undefined,
    has_key_result: optionalBoolean(input.hasKeyResult),
    publication_id: input.publicationId.trim() || undefined,
    conference: input.conference.trim() || undefined,
    disclosed_from: input.disclosedFrom || undefined,
    disclosed_to: input.disclosedTo || undefined,
    sort_by: input.sortBy,
    sort_direction: input.sortDirection,
    sort: effectiveSort(input.sort, input.sortBy, input.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: input.displayMode,
    analysis_view: input.analysisView,
  };
}

export function hasTrialSearchFilter(input: TrialSavedSearchInput): boolean {
  const query = savedClinicalTrialQuery(input);
  return Object.entries(query).some(
    ([key, value]) =>
      !["sort_by", "sort_direction", "sort", "display_mode", "analysis_view"].includes(key) && value !== undefined,
  );
}

export async function saveClinicalTrialSearch({
  name,
  input,
  shared,
  monitor,
}: {
  name: string;
  input: TrialSavedSearchInput;
  shared: boolean;
  monitor: boolean;
}): Promise<{ message: string }> {
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query_type: "clinical_trial_search",
        query: savedClinicalTrialQuery(input),
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
  return { message: monitor ? "临床试验检索已保存并启用监控" : "临床试验检索已保存" };
}

export async function searchTrials(
  query: string,
  registry: string,
  status: string,
  phase: string,
  studyType: string,
  acronym: string,
  initiationType: string,
  therapyLine: string,
  hasResults: string,
  resultEvaluation: string,
  resultsPostedFrom: string,
  resultsPostedTo: string,
  investigationalDrug: string,
  combinationDrug: string,
  investigationalTarget: string,
  combinationTarget: string,
  investigationalDrugEntityIds: string[],
  combinationDrugEntityIds: string[],
  investigationalTargetEntityIds: string[],
  combinationTargetEntityIds: string[],
  linkedDrugModalities: string[],
  linkedDrugInnovationTypes: string[],
  linkedDrugCategories: string[],
  linkedDrugProgramTags: string[],
  linkedDrugGlobalPhase: string,
  linkedDrugOrganizationCountryRegion: string,
  roleEntityId: string,
  roleEntityIds: string[],
  roleEntityRole: string,
  hasKeyResult: string,
  publicationId: string,
  conference: string,
  disclosedFrom: string,
  disclosedTo: string,
  sortBy: TrialSortField,
  sortDirection: SortDirection,
  offset: number,
  signal?: AbortSignal,
  sort?: readonly SortCriterion<TrialSortField>[],
): Promise<ClinicalTrialSearchResult> {
  return contractRequest(
    TrialsService.searchTrialsApiV1TrialsGet({
      q: query.trim() || undefined,
      registry: registry || undefined,
      status: status || undefined,
      phase: phase || undefined,
      studyType: studyType || undefined,
      acronym: acronym.trim() || undefined,
      initiationType: asTrialInitiationType(initiationType),
      therapyLine: asTrialTherapyLine(therapyLine),
      hasResults: hasResults === "true" ? true : hasResults === "false" ? false : undefined,
      resultEvaluation: asTrialResultEvaluation(resultEvaluation),
      resultsPostedFrom: resultsPostedFrom ? `${resultsPostedFrom}T00:00:00.000Z` : undefined,
      resultsPostedTo: resultsPostedTo ? `${resultsPostedTo}T23:59:59.999Z` : undefined,
      investigationalDrug: investigationalDrug.trim() || undefined,
      combinationDrug: combinationDrug.trim() || undefined,
      investigationalTarget: investigationalTarget.trim() || undefined,
      combinationTarget: combinationTarget.trim() || undefined,
      investigationalDrugEntityIds: investigationalDrugEntityIds.length
        ? [...new Set(investigationalDrugEntityIds)].sort()
        : undefined,
      combinationDrugEntityIds: combinationDrugEntityIds.length
        ? [...new Set(combinationDrugEntityIds)].sort()
        : undefined,
      investigationalTargetEntityIds: investigationalTargetEntityIds.length
        ? [...new Set(investigationalTargetEntityIds)].sort()
        : undefined,
      combinationTargetEntityIds: combinationTargetEntityIds.length
        ? [...new Set(combinationTargetEntityIds)].sort()
        : undefined,
      linkedDrugModality: linkedDrugModalities.length ? [...new Set(linkedDrugModalities)].sort() : undefined,
      linkedDrugInnovationType: linkedDrugInnovationTypes.length
        ? [...new Set(linkedDrugInnovationTypes)].sort()
        : undefined,
      linkedDrugCategory: linkedDrugCategories.length ? [...new Set(linkedDrugCategories)].sort() : undefined,
      linkedDrugProgramTag: linkedDrugProgramTags.length ? [...new Set(linkedDrugProgramTags)].sort() : undefined,
      linkedDrugGlobalPhase: asDevelopmentPhase(linkedDrugGlobalPhase),
      linkedDrugOrganizationCountryRegion: linkedDrugOrganizationCountryRegion.trim() || undefined,
      roleEntityId: roleEntityIds.length ? undefined : roleEntityId || undefined,
      roleEntityIds: roleEntityIds.length ? [...new Set(roleEntityIds)].sort() : undefined,
      roleEntityRole: roleEntityIds.length || roleEntityId ? asTrialEntityRole(roleEntityRole) : undefined,
      hasKeyResult: hasKeyResult === "true" ? true : hasKeyResult === "false" ? false : undefined,
      publicationId: publicationId.trim() || undefined,
      conference: conference.trim() || undefined,
      disclosedFrom: disclosedFrom ? `${disclosedFrom}T00:00:00.000Z` : undefined,
      disclosedTo: disclosedTo ? `${disclosedTo}T23:59:59.999Z` : undefined,
      sort: effectiveSort(sort, sortBy, sortDirection).map((criterion) => `${criterion.field}:${criterion.direction}`),
      limit: 100,
      offset,
    }),
    signal,
  );
}

export async function loadTrialDetail(trialId: string, signal?: AbortSignal): Promise<ClinicalTrialDetailRead> {
  return contractRequest(TrialsService.getTrialDetailApiV1TrialsTrialIdGet({ trialId }), signal);
}
