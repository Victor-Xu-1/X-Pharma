import { parseSortTokens, type SortCriterion, type SortDirection } from "./contracts/sorting";
import type { UserRole } from "./types";

export type WorkbenchKey = "research" | "internal";

export const targetDossierSections = [
  "overview",
  "relationships",
  "evidence",
  "activities",
  "sar",
  "pipeline",
  "trials",
  "patents",
  "deals",
  "regulatory",
  "news",
  "structures",
] as const;
export type TargetDossierSection = (typeof targetDossierSections)[number];

export const drugDossierSections = [
  "overview",
  "pipeline",
  "relationships",
  "activities",
  "trials",
  "patents",
  "deals",
  "regulatory",
  "news",
  "structures",
] as const;
export type DrugDossierSection = (typeof drugDossierSections)[number];

export const companyDossierSections = [
  "overview",
  "pipeline",
  "timeline",
  "deals",
  "relationships",
  "trials",
  "patents",
  "regulatory",
  "news",
] as const;
export type CompanyDossierSection = (typeof companyDossierSections)[number];

export const diseaseDossierSections = [
  "overview",
  "epidemiology",
  "pipeline",
  "evidence",
  "trials",
  "patents",
  "deals",
  "regulatory",
  "news",
  "relationships",
] as const;
export type DiseaseDossierSection = (typeof diseaseDossierSections)[number];

export const trialDossierSections = ["overview", "design", "outcomes", "timeline"] as const;
export type TrialDossierSection = (typeof trialDossierSections)[number];

export const patentDossierSections = ["overview", "timeline", "relationships"] as const;
export type PatentDossierSection = (typeof patentDossierSections)[number];

export const dealDossierSections = ["overview", "parties", "assets", "rights", "terms"] as const;
export type DealDossierSection = (typeof dealDossierSections)[number];

export const entityDossierSections = [
  "overview",
  "company_intelligence",
  "relationships",
  "programs",
  "activities",
  "clinical_trials",
  "patents",
  "deals",
  "regulatory_events",
  "news_events",
  "structures",
] as const;
export type EntityDossierSection = (typeof entityDossierSections)[number];
export type KnowledgePanel = "document" | "coverage";
export type MonitoringTab = "alerts" | "topics" | "searches";

const targetDossierSectionSet = new Set<string>(targetDossierSections);
const drugDossierSectionSet = new Set<string>(drugDossierSections);
const companyDossierSectionSet = new Set<string>(companyDossierSections);
const diseaseDossierSectionSet = new Set<string>(diseaseDossierSections);
const trialDossierSectionSet = new Set<string>(trialDossierSections);
const patentDossierSectionSet = new Set<string>(patentDossierSections);
const dealDossierSectionSet = new Set<string>(dealDossierSections);
const entityDossierSectionSet = new Set<string>(entityDossierSections);
const monitoringTabSet = new Set<string>(["alerts", "topics", "searches"]);

export type ViewKey =
  | "overview"
  | "explorer"
  | "chemistry"
  | "pipeline"
  | "trials"
  | "patents"
  | "deals"
  | "regulatory"
  | "epidemiology"
  | "news"
  | "target"
  | "drug"
  | "company"
  | "disease"
  | "entity"
  | "evidence"
  | "knowledge"
  | "monitoring"
  | "collections"
  | "factory"
  | "governance"
  | "commercial"
  | "enterprise";

export interface WorkspaceLocation {
  workbench: WorkbenchKey;
  view: ViewKey;
  query: string;
  entityType: string;
  entityTypes?: string[];
  reviewStatus: string;
  entitySort?: SortCriterion[];
  entitySortBy?: string;
  entitySortDirection?: SortDirection;
  explorerDisplayMode?: "list" | "landscape";
  explorerAnalysisView?: "chart" | "table";
  entityId: string | null;
  invalidEntityId: boolean;
  returnTo?: string;
  chemistrySavedSearchId?: string | null;
  invalidChemistrySavedSearchId?: boolean;
  knowledgePageId?: string | null;
  invalidKnowledgePageId?: boolean;
  knowledgePanel?: KnowledgePanel;
  knowledgeVersionNumber?: number | null;
  monitoringTab?: MonitoringTab;
  evidenceDatasetKeys?: string[];
  evidenceDocumentId?: string | null;
  evidenceChunkIndex?: number | null;
  targetSection?: TargetDossierSection;
  drugSection?: DrugDossierSection;
  companySection?: CompanyDossierSection;
  diseaseSection?: DiseaseDossierSection;
  entitySection?: EntityDossierSection;
  pipelineModalities?: string[];
  pipelineInnovationTypes?: string[];
  pipelineTherapeuticAreas?: string[];
  pipelineDrugCategories?: string[];
  pipelineProgramStatus?: string;
  pipelineOrganizationRole?: string;
  pipelineOrganizationType?: string;
  pipelineOrganizationCountryRegion?: string;
  phase?: string;
  geography?: string;
  pipelineStatusDateFrom?: string;
  pipelineStatusDateTo?: string;
  pipelineDrugEntityId?: string;
  pipelineTargetEntityId?: string;
  pipelineTargetCombinationKey?: string;
  pipelineDiseaseEntityId?: string;
  pipelineOrganizationEntityId?: string;
  pipelineGlobalPhase?: string;
  pipelineChinaPhase?: string;
  pipelineGlobalPhaseStartedFrom?: string;
  pipelineGlobalPhaseStartedTo?: string;
  pipelineChinaPhaseStartedFrom?: string;
  pipelineChinaPhaseStartedTo?: string;
  pipelineDevelopmentRightsRegion?: string;
  pipelineCommercializationRightsRegion?: string;
  pipelineProgramTags?: string[];
  pipelineMilestoneType?: string;
  pipelineMilestoneFrom?: string;
  pipelineMilestoneTo?: string;
  pipelineHasClinicalResults?: "" | "true" | "false";
  pipelineClinicalResultEvaluation?: string;
  pipelineHasDeal?: "" | "true" | "false";
  pipelineDealCurrency?: string;
  pipelineDealTotalPotentialAmountMin?: string;
  pipelineDealTotalPotentialAmountMax?: string;
  pipelineSort?: SortCriterion[];
  pipelineSortBy?: string;
  pipelineSortDirection?: SortDirection;
  pipelineDisplayMode?: "list" | "landscape";
  pipelineResultGrain?: "program" | "drug";
  targetPipelineDisplayMode?: "drug" | "program" | "landscape";
  pipelineAnalysisDimension?:
    | "all"
    | "global_phase"
    | "china_phase"
    | "targets"
    | "target_combinations"
    | "diseases"
    | "organizations"
    | "modality"
    | "geography";
  pipelineAnalysisView?: "chart" | "table";
  pipelineAnalysisLimit?: 5 | 8 | 20 | 50 | 100 | 200;
  pipelineAnalysisStageScope?: "overall" | "global" | "china";
  pipelineTargetAggregation?: "all" | "primary";
  registry?: string;
  trialStatus?: string;
  trialPhase?: string;
  studyType?: string;
  trialAcronym?: string;
  trialInitiationType?: string;
  trialTherapyLine?: string;
  trialHasResults?: string;
  trialResultEvaluation?: string;
  trialResultsPostedFrom?: string;
  trialResultsPostedTo?: string;
  trialInvestigationalDrug?: string;
  trialCombinationDrug?: string;
  trialInvestigationalTarget?: string;
  trialCombinationTarget?: string;
  trialInvestigationalDrugEntityIds?: string[];
  trialCombinationDrugEntityIds?: string[];
  trialInvestigationalTargetEntityIds?: string[];
  trialCombinationTargetEntityIds?: string[];
  trialLinkedDrugModalities?: string[];
  trialLinkedDrugInnovationTypes?: string[];
  trialLinkedDrugCategories?: string[];
  trialLinkedDrugProgramTags?: string[];
  trialLinkedDrugGlobalPhase?: string;
  trialLinkedDrugOrganizationCountryRegion?: string;
  trialRoleEntityId?: string;
  trialRoleEntityIds?: string[];
  trialRoleEntityRole?: string;
  trialHasKeyResult?: string;
  trialPublicationId?: string;
  trialConference?: string;
  trialDisclosedFrom?: string;
  trialDisclosedTo?: string;
  trialSort?: SortCriterion[];
  trialSortBy?: string;
  trialSortDirection?: SortDirection;
  trialDisplayMode?: "list" | "landscape";
  trialAnalysisView?: "chart" | "table";
  trialId?: string | null;
  invalidTrialId?: boolean;
  trialSection?: TrialDossierSection;
  applicant?: string;
  legalStatus?: string;
  patentSort?: SortCriterion[];
  patentSortBy?: string;
  patentEntityId?: string;
  patentPriorityFrom?: string;
  patentPriorityTo?: string;
  patentExpirationFrom?: string;
  patentExpirationTo?: string;
  patentDisplayMode?: "list" | "landscape";
  patentAnalysisView?: "chart" | "table";
  regulatoryDisplayMode?: "list" | "landscape";
  regulatoryAnalysisView?: "chart" | "table";
  patentSortDirection?: SortDirection;
  patentId?: string | null;
  invalidPatentId?: boolean;
  patentSection?: PatentDossierSection;
  dealType?: string;
  dealStatus?: string;
  dealDirection?: string;
  dealDirectionReferenceJurisdiction?: string;
  dealTerritory?: string;
  dealAssetEntityId?: string;
  dealTargetEntityId?: string;
  dealDiseaseEntityId?: string;
  dealAssetModalities?: string[];
  dealAssetProgramTags?: string[];
  dealParty?: string;
  dealPartyEntityId?: string;
  dealPartyRole?: string;
  dealPartyCountryRegion?: string;
  dealPartyOrganizationType?: string;
  dealDevelopmentPhaseAtTransaction?: string;
  dealCurrentDevelopmentPhase?: string;
  dealRightType?: string;
  dealRightsTerritory?: string;
  dealCurrency?: string;
  dealAnnouncedFrom?: string;
  dealAnnouncedTo?: string;
  dealTerminatedFrom?: string;
  dealTerminatedTo?: string;
  dealSourceUpdatedFrom?: string;
  dealSourceUpdatedTo?: string;
  dealUpfrontAmountMin?: string;
  dealUpfrontAmountMax?: string;
  dealTotalPotentialAmountMin?: string;
  dealTotalPotentialAmountMax?: string;
  dealSort?: SortCriterion[];
  dealSortBy?: string;
  dealSortDirection?: SortDirection;
  dealDisplayMode?: "list" | "landscape";
  dealAnalysisDimension?:
    | "all"
    | "deal_type"
    | "status"
    | "direction"
    | "territory"
    | "currency"
    | "asset_modality"
    | "transaction_phase"
    | "current_phase"
    | "party_country"
    | "rights_territory";
  dealAnalysisView?: "chart" | "table";
  dealAnalysisLimit?: 5 | 8 | 20 | 50;
  dealId?: string | null;
  invalidDealId?: boolean;
  dealSection?: DealDossierSection;
  regulatoryAgency?: string;
  regulatoryJurisdiction?: string;
  regulatoryEventType?: string;
  regulatoryStatus?: string;
  regulatoryDesignationType?: string;
  regulatoryLabelChangeType?: string;
  regulatoryBoxedWarning?: string;
  regulatorySafetySignalType?: string;
  regulatorySafetySeverity?: string;
  regulatorySafetyStatus?: string;
  regulatoryDecisionFrom?: string;
  regulatoryDecisionTo?: string;
  regulatorySourceUpdatedFrom?: string;
  regulatorySourceUpdatedTo?: string;
  regulatorySort?: SortCriterion[];
  regulatorySortBy?: string;
  regulatorySortDirection?: SortDirection;
  regulatoryEventId?: string | null;
  invalidRegulatoryEventId?: boolean;
  regulatoryCompareIds?: string[];
  epidemiologyMeasure?: string;
  epidemiologyDiseaseEntityId?: string;
  epidemiologyGeography?: string;
  epidemiologyUnit?: string;
  epidemiologyPatientPopulationId?: string;
  epidemiologyPopulationScope?: string;
  epidemiologyAgeGroup?: string;
  epidemiologySex?: string;
  epidemiologyPeriodStartFrom?: string;
  epidemiologyPeriodEndTo?: string;
  epidemiologySort?: SortCriterion[];
  epidemiologySortBy?: string;
  epidemiologySortDirection?: SortDirection;
  newsEventType?: string;
  newsPublisher?: string;
  newsLanguage?: string;
  newsVenue?: string;
  newsPublishedFrom?: string;
  newsPublishedTo?: string;
  newsContentScope?: "" | "research";
  newsEntityId?: string;
  newsDisplayMode?: "list" | "timeline" | "landscape";
  newsAnalysisView?: "chart" | "table";
  epidemiologyDisplayMode?: "list" | "landscape";
  epidemiologyAnalysisView?: "chart" | "table";
  newsSort?: SortCriterion[];
  newsSortBy?: string;
  newsSortDirection?: SortDirection;
  newsEventId?: string | null;
  invalidNewsEventId?: boolean;
  collectionId?: string | null;
  invalidCollectionId?: boolean;
  collectionCompareEntityIds?: string[];
  offset?: number;
}

const workbenchPaths: Record<WorkbenchKey, string> = {
  research: "/workspace/research",
  internal: "/workspace/internal",
};

export function workbenchPath(workbench: WorkbenchKey): string {
  return workbenchPaths[workbench];
}

const workbenchDefaults: Record<WorkbenchKey, ViewKey> = {
  research: "explorer",
  internal: "factory",
};

const viewWorkbenches: Record<ViewKey, WorkbenchKey> = {
  overview: "research",
  explorer: "research",
  chemistry: "research",
  pipeline: "research",
  trials: "research",
  patents: "research",
  deals: "research",
  regulatory: "research",
  epidemiology: "research",
  news: "research",
  target: "research",
  drug: "research",
  company: "research",
  disease: "research",
  entity: "research",
  evidence: "research",
  knowledge: "research",
  monitoring: "research",
  collections: "research",
  factory: "internal",
  governance: "internal",
  commercial: "internal",
  enterprise: "internal",
};

const views = new Set<ViewKey>([
  "overview",
  "explorer",
  "chemistry",
  "pipeline",
  "trials",
  "patents",
  "deals",
  "regulatory",
  "epidemiology",
  "news",
  "target",
  "drug",
  "company",
  "disease",
  "entity",
  "evidence",
  "knowledge",
  "monitoring",
  "collections",
  "factory",
  "governance",
  "commercial",
  "enterprise",
]);

const restrictedViews: Partial<Record<ViewKey, ReadonlySet<UserRole>>> = {
  factory: new Set(["admin", "analyst"]),
  governance: new Set(["admin", "analyst"]),
  commercial: new Set(["admin"]),
  enterprise: new Set(["admin"]),
};

const entityIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const maximumReturnPathLength = 4_096;

const entityDossierViews: ReadonlySet<ViewKey> = new Set(["drug", "target", "company", "disease", "entity"]);

/** Parse only bounded, same-workbench context; never follow a referrer or browser history blindly. */
export function researchReturnLocation(value: string | null | undefined): WorkspaceLocation | null {
  return parseResearchReturnLocation(value, 3);
}

function parseResearchReturnLocation(
  value: string | null | undefined,
  remainingDepth: number,
): WorkspaceLocation | null {
  if (
    !value ||
    value.length > maximumReturnPathLength ||
    !value.startsWith("/workspace/research?") ||
    /[\\#]/.test(value) ||
    Array.from(value).some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)
  ) {
    return null;
  }
  const url = new URL(value, "https://pharma.local");
  if (url.origin !== "https://pharma.local" || url.pathname !== "/workspace/research") return null;
  const requestedView = url.searchParams.get("view") as ViewKey;
  if (
    url.searchParams.getAll("view").length !== 1 ||
    !views.has(requestedView) ||
    workbenchForView(requestedView) !== "research" ||
    url.searchParams.getAll("from").length > 1
  ) {
    return null;
  }
  const nestedPath = url.searchParams.get("from");
  // Strip before the ordinary parser so nested untrusted input cannot create unbounded recursion.
  url.searchParams.delete("from");
  const parsed = parseWorkbenchLocation("research", url.search);
  if (
    parsed.invalidEntityId ||
    parsed.invalidTrialId ||
    parsed.invalidPatentId ||
    parsed.invalidDealId ||
    parsed.invalidRegulatoryEventId ||
    parsed.invalidNewsEventId ||
    parsed.invalidCollectionId ||
    parsed.invalidChemistrySavedSearchId ||
    parsed.invalidKnowledgePageId ||
    (entityDossierViews.has(parsed.view) && !parsed.entityId) ||
    (parsed.view === "collections" && !parsed.collectionId)
  ) {
    return null;
  }
  const nested = remainingDepth > 1 ? parseResearchReturnLocation(nestedPath, remainingDepth - 1) : null;
  if (nested) parsed.returnTo = workspaceUrl(nested);
  return workspaceUrl(parsed).length <= maximumReturnPathLength ? parsed : null;
}

function boundedResearchReturnPath(value: string | null | undefined): string | undefined {
  const parsed = researchReturnLocation(value);
  return parsed ? workspaceUrl(parsed) : undefined;
}
function boundedEvidenceDocumentId(value: string | null): string | null {
  const normalized = value?.trim() ?? "";
  const hasControlCharacter = Array.from(normalized).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint < 32 || codePoint === 127;
  });
  if (!normalized || normalized.length > 240 || hasControlCharacter) return null;
  return normalized;
}

function boundedTargetCombinationKey(value: string | null | undefined): string {
  if (!value) return "";
  const ids = value
    .split("|")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  if (!ids.length || ids.length > 20 || ids.some((item) => !entityIdPattern.test(item))) return "";
  const unique = Array.from(new Set(ids)).sort();
  return unique.length === ids.length ? unique.join("|") : "";
}
const entityTypeValues = [
  "target",
  "drug",
  "organization",
  "disease",
  "clinical_trial",
  "patent",
  "transaction",
  "product",
  "technology",
  "person",
] as const;
const entityTypes = new Set<string>(entityTypeValues);
const reviewStatuses = new Set(["draft", "verified", "rejected", "superseded"]);
const entitySortFields = new Set(["relevance", "name", "entity_type", "updated_at"]);
const developmentPhases = new Set([
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
const pipelineOrganizationRoles = new Set([
  "originator",
  "collaborator",
  "licensee",
  "licensor",
  "manufacturer",
  "other",
]);
const pipelineSortFields = new Set([
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
]);
const pipelineAnalysisDimensions = new Set([
  "all",
  "global_phase",
  "china_phase",
  "targets",
  "target_combinations",
  "diseases",
  "organizations",
  "modality",
  "geography",
]);
const pipelineAnalysisLimits = new Set([5, 8, 20, 50, 100, 200]);
const pipelineAnalysisStageScopes = new Set(["overall", "global", "china"]);
const pipelineTargetAggregations = new Set(["all", "primary"]);
const pipelineResultGrains = new Set(["program", "drug"]);
const trialSortFields = new Set([
  "last_update_posted",
  "registry_id",
  "has_results",
  "result_evaluation",
  "overall_status",
  "enrollment",
  "study_type",
  "acronym",
  "initiation_type",
]);
const patentSortFields = new Set(["priority_date", "family_identifier", "legal_status", "expiration_date"]);
const dealSortFields = new Set([
  "announced_at",
  "name",
  "deal_type",
  "status",
  "direction",
  "territory",
  "upfront_amount",
  "total_potential_amount",
]);
const dealAmountSortFields = new Set(["upfront_amount", "total_potential_amount"]);
const dealAnalysisDimensions = new Set([
  "all",
  "deal_type",
  "status",
  "direction",
  "territory",
  "currency",
  "asset_modality",
  "transaction_phase",
  "current_phase",
  "party_country",
  "rights_territory",
]);
const dealAnalysisLimits = new Set([5, 8, 20, 50]);
const regulatorySortFields = new Set([
  "decision_date",
  "title",
  "agency",
  "jurisdiction",
  "event_type",
  "status",
  "subject",
  "source_updated_at",
]);
const epidemiologySortFields = new Set([
  "period_end",
  "period_start",
  "disease",
  "measure",
  "value",
  "geography",
  "unit",
  "publisher",
  "sample_size",
]);
const newsSortFields = new Set(["published_at", "title", "event_type", "publisher", "venue"]);
const trialResultEvaluations = new Set([
  "unfavorable",
  "not_superior",
  "non_inferior",
  "similar",
  "positive",
  "superior",
  "terminated",
]);
const trialEntityRoles = new Set([
  "investigational_drug",
  "combination_drug",
  "investigational_target",
  "combination_target",
]);
const trialInitiationTypes = new Set(["iit", "ist"]);
const trialTherapyLines = new Set([
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
const dealStatuses = new Set(["announced", "active", "completed", "terminated", "withdrawn", "superseded", "unknown"]);
const dealDirections = new Set(["domestic", "inbound", "outbound", "cross_border", "global", "undisclosed"]);
const dealPartyRoles = new Set([
  "licensor",
  "licensee",
  "seller",
  "buyer",
  "acquirer",
  "target",
  "partner",
  "investor",
  "investee",
  "other",
]);
const dealRightTypes = new Set([
  "research",
  "development",
  "manufacturing",
  "commercialization",
  "co_development",
  "co_promotion",
  "distribution",
  "option",
  "other",
]);
const regulatoryDesignationTypes = new Set([
  "breakthrough_therapy",
  "fast_track",
  "priority_review",
  "accelerated_approval",
  "orphan_drug",
  "prime",
  "sakigake",
  "conditional_marketing_authorisation",
  "other",
]);
const regulatoryLabelChangeTypes = new Set([
  "initial_label",
  "indication_expansion",
  "population_expansion",
  "restriction",
  "dosing_update",
  "administration_update",
  "safety_update",
  "boxed_warning",
  "contraindication",
  "other",
]);
const regulatorySafetySignalTypes = new Set([
  "adverse_event",
  "boxed_warning",
  "contraindication",
  "risk_management",
  "recall",
  "clinical_hold",
  "postmarketing_requirement",
  "other",
]);
const regulatorySafetySeverities = new Set([
  "informational",
  "moderate",
  "serious",
  "severe",
  "life_threatening",
  "fatal",
  "unknown",
]);
const regulatorySafetyStatuses = new Set([
  "detected",
  "under_evaluation",
  "confirmed",
  "monitoring",
  "resolved",
  "withdrawn",
  "unknown",
]);

function boundedIsoDate(value: string | null): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value ? "" : value;
}

function boundedAmount(value: string | null): string {
  if (!value || !/^\d+(?:\.\d{1,2})?$/.test(value)) return "";
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1_000_000_000_000_000 ? value : "";
}

function boundedEntityIdList(value: string | null, maximum = 4): string[] {
  if (!value) return [];
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter((item) => entityIdPattern.test(item)),
    ),
  ).slice(0, maximum);
}

function boundedRepeatedValues(params: URLSearchParams, name: string, maxLength: number, maximum = 20): string[] {
  return Array.from(
    new Set(
      params
        .getAll(name)
        .map((item) => item.trim())
        .filter((item) => item.length > 0 && item.length <= maxLength),
    ),
  ).slice(0, maximum);
}

function boundedRepeatedEntityIds(params: URLSearchParams, name: string, maximum = 20): string[] {
  return boundedRepeatedValues(params, name, 36, maximum)
    .map((item) => item.toLowerCase())
    .filter((item) => entityIdPattern.test(item))
    .sort();
}

function locationSort(
  params: URLSearchParams,
  allowedFields: ReadonlySet<string>,
  defaultField: string,
  defaultDirection: SortDirection = "desc",
): SortCriterion[] {
  const legacyField = params.get("sort_by");
  const fallback = {
    field: legacyField && allowedFields.has(legacyField) ? legacyField : defaultField,
    direction: params.get("sort_direction") === "asc" ? ("asc" as const) : defaultDirection,
  };
  return parseSortTokens(params.getAll("sort"), allowedFields, fallback);
}

function appendLocationSort(
  params: URLSearchParams,
  sort: readonly SortCriterion[] | undefined,
  allowedFields: ReadonlySet<string>,
  legacyField: string | undefined,
  legacyDirection: SortDirection | undefined,
  defaultField: string,
  defaultDirection: SortDirection = "desc",
) {
  const fallback = {
    field: legacyField && allowedFields.has(legacyField) ? legacyField : defaultField,
    direction: legacyDirection ?? defaultDirection,
  };
  const tokens = (sort ?? []).map((criterion) => `${criterion.field}:${criterion.direction}`);
  const criteria = parseSortTokens(tokens, allowedFields, fallback);
  if (criteria.length === 1 && criteria[0]?.field === defaultField && criteria[0]?.direction === defaultDirection)
    return;
  for (const criterion of criteria) {
    params.append("sort", `${criterion.field}:${criterion.direction}`);
  }
}

export function canAccessView(view: ViewKey, role: UserRole): boolean {
  return restrictedViews[view]?.has(role) ?? true;
}

export function canAccessWorkbench(workbench: WorkbenchKey, role: UserRole): boolean {
  return workbench === "research" || role === "admin" || role === "analyst";
}

export function workbenchForView(view: ViewKey): WorkbenchKey {
  return viewWorkbenches[view];
}

export function defaultViewForWorkbench(workbench: WorkbenchKey): ViewKey {
  return workbenchDefaults[workbench];
}

export function parseWorkbenchLocation(workbench: WorkbenchKey, search = ""): WorkspaceLocation {
  const params = new URLSearchParams(search);
  const requestedView = params.get("view");
  const validRequestedView = requestedView && views.has(requestedView as ViewKey) ? (requestedView as ViewKey) : null;
  const view =
    validRequestedView && viewWorkbenches[validRequestedView] === workbench
      ? validRequestedView
      : workbenchDefaults[workbench];
  const query =
    view === "explorer" ||
    view === "target" ||
    view === "drug" ||
    view === "company" ||
    view === "disease" ||
    view === "entity" ||
    view === "pipeline" ||
    view === "trials" ||
    view === "patents" ||
    view === "deals" ||
    view === "regulatory" ||
    view === "epidemiology" ||
    view === "news" ||
    view === "knowledge" ||
    view === "evidence"
      ? (params.get("q") ?? "").trim().slice(0, 500)
      : "";
  const requestedEntityType = view === "explorer" ? params.get("type") : null;
  const requestedEntityTypes =
    view === "explorer"
      ? (params.get("types") ?? "")
          .split(",")
          .map((value) => value.trim())
          .filter((value) => entityTypes.has(value))
      : [];
  const selectedEntityTypes = Array.from(
    new Set(
      requestedEntityTypes.length
        ? requestedEntityTypes
        : requestedEntityType && entityTypes.has(requestedEntityType)
          ? [requestedEntityType]
          : [],
    ),
  )
    .slice(0, 10)
    .sort(
      (left, right) =>
        entityTypeValues.indexOf(left as (typeof entityTypeValues)[number]) -
        entityTypeValues.indexOf(right as (typeof entityTypeValues)[number]),
    );
  const entityType = selectedEntityTypes.length === 1 ? (selectedEntityTypes[0] ?? "") : "";
  const requestedReviewStatus = view === "explorer" ? params.get("review") : null;
  const reviewStatus = requestedReviewStatus && reviewStatuses.has(requestedReviewStatus) ? requestedReviewStatus : "";
  const entitySort = locationSort(params, entitySortFields, "relevance");
  const pipelineSort = locationSort(params, pipelineSortFields, "status_date");
  const trialSort = locationSort(params, trialSortFields, "last_update_posted");
  const patentSort = locationSort(params, patentSortFields, "priority_date");
  const requestedDealSort = locationSort(params, dealSortFields, "announced_at");
  const dealSort =
    requestedDealSort.some((criterion) => dealAmountSortFields.has(criterion.field)) &&
    !/^[A-Z]{3}$/.test(params.get("currency") ?? "")
      ? [{ field: "announced_at", direction: requestedDealSort[0]?.direction ?? ("desc" as const) }]
      : requestedDealSort;
  const regulatorySort = locationSort(params, regulatorySortFields, "decision_date");
  const epidemiologySort = locationSort(params, epidemiologySortFields, "period_end");
  const newsSort = locationSort(params, newsSortFields, "published_at");
  const explorerFilters =
    view === "explorer"
      ? {
          entitySort,
          entitySortBy: entitySort[0]?.field ?? "relevance",
          entitySortDirection: entitySort[0]?.direction ?? "desc",
          explorerDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          explorerAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          entityTypes: selectedEntityTypes,
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawEntityId =
    view === "explorer" ||
    view === "target" ||
    view === "drug" ||
    view === "company" ||
    view === "disease" ||
    view === "entity"
      ? params.get("entity")
      : null;
  const entityId = rawEntityId && entityIdPattern.test(rawEntityId) ? rawEntityId.toLowerCase() : null;
  const rawChemistrySavedSearchId = view === "chemistry" ? params.get("saved") : null;
  const chemistrySavedSearchId =
    rawChemistrySavedSearchId && entityIdPattern.test(rawChemistrySavedSearchId)
      ? rawChemistrySavedSearchId.toLowerCase()
      : null;
  const chemistryFilters =
    view === "chemistry"
      ? {
          chemistrySavedSearchId,
          invalidChemistrySavedSearchId: rawChemistrySavedSearchId !== null && chemistrySavedSearchId === null,
        }
      : {};
  const requestedSection = params.get("section") ?? "overview";
  const dossierSection =
    view === "target"
      ? {
          targetSection: targetDossierSectionSet.has(requestedSection)
            ? (requestedSection as TargetDossierSection)
            : "overview",
        }
      : view === "drug"
        ? {
            drugSection: drugDossierSectionSet.has(requestedSection)
              ? (requestedSection as DrugDossierSection)
              : "overview",
            offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
          }
        : view === "company"
          ? {
              companySection: companyDossierSectionSet.has(requestedSection)
                ? (requestedSection as CompanyDossierSection)
                : "overview",
            }
          : view === "disease"
            ? {
                diseaseSection: diseaseDossierSectionSet.has(requestedSection)
                  ? (requestedSection as DiseaseDossierSection)
                  : "overview",
              }
            : view === "entity"
              ? {
                  entitySection: entityDossierSectionSet.has(requestedSection)
                    ? (requestedSection as EntityDossierSection)
                    : "overview",
                }
              : {};
  const returnTo = workbench === "research" ? boundedResearchReturnPath(params.get("from")) : undefined;
  const pipelineFilters =
    view === "pipeline" || (view === "target" && requestedSection === "pipeline")
      ? {
          pipelineModalities: boundedRepeatedValues(params, "modality", 120),
          pipelineInnovationTypes: boundedRepeatedValues(params, "innovation_type", 120),
          pipelineTherapeuticAreas: boundedRepeatedValues(params, "therapeutic_area", 120),
          pipelineDrugCategories: boundedRepeatedValues(params, "drug_category", 120),
          pipelineProgramStatus: ["active", "inactive", "unknown", "all"].includes(params.get("program_status") ?? "")
            ? (params.get("program_status") ?? "")
            : view === "target"
              ? undefined
              : "",
          pipelineOrganizationRole: pipelineOrganizationRoles.has(params.get("organization_role") ?? "")
            ? (params.get("organization_role") ?? "")
            : "",
          pipelineOrganizationType: (params.get("organization_type") ?? "").trim().slice(0, 120),
          pipelineOrganizationCountryRegion: (params.get("organization_country_region") ?? "").trim().slice(0, 120),
          phase: developmentPhases.has(params.get("phase") ?? "") ? (params.get("phase") ?? "") : "",
          geography: (params.get("geography") ?? "").trim().slice(0, 120),
          pipelineStatusDateFrom: boundedIsoDate(params.get("status_date_from")),
          pipelineStatusDateTo: boundedIsoDate(params.get("status_date_to")),
          pipelineDrugEntityId:
            params.get("drug_entity_id") && entityIdPattern.test(params.get("drug_entity_id") ?? "")
              ? (params.get("drug_entity_id") ?? "").toLowerCase()
              : "",
          pipelineTargetEntityId:
            params.get("target_entity_id") && entityIdPattern.test(params.get("target_entity_id") ?? "")
              ? (params.get("target_entity_id") ?? "").toLowerCase()
              : "",
          pipelineTargetCombinationKey: boundedTargetCombinationKey(params.get("target_combination_key")),
          pipelineDiseaseEntityId:
            params.get("disease_entity_id") && entityIdPattern.test(params.get("disease_entity_id") ?? "")
              ? (params.get("disease_entity_id") ?? "").toLowerCase()
              : "",
          pipelineOrganizationEntityId:
            params.get("organization_entity_id") && entityIdPattern.test(params.get("organization_entity_id") ?? "")
              ? (params.get("organization_entity_id") ?? "").toLowerCase()
              : "",
          pipelineGlobalPhase: developmentPhases.has(params.get("global_phase") ?? "")
            ? (params.get("global_phase") ?? "")
            : "",
          pipelineChinaPhase: developmentPhases.has(params.get("china_phase") ?? "")
            ? (params.get("china_phase") ?? "")
            : "",
          pipelineGlobalPhaseStartedFrom: boundedIsoDate(params.get("global_phase_started_from")),
          pipelineGlobalPhaseStartedTo: boundedIsoDate(params.get("global_phase_started_to")),
          pipelineChinaPhaseStartedFrom: boundedIsoDate(params.get("china_phase_started_from")),
          pipelineChinaPhaseStartedTo: boundedIsoDate(params.get("china_phase_started_to")),
          pipelineDevelopmentRightsRegion: (params.get("development_rights_region") ?? "").trim().slice(0, 240),
          pipelineCommercializationRightsRegion: (params.get("commercialization_rights_region") ?? "")
            .trim()
            .slice(0, 240),
          pipelineProgramTags: boundedRepeatedValues(params, "program_tag", 240),
          pipelineMilestoneType: (params.get("milestone_type") ?? "").trim().slice(0, 120),
          pipelineMilestoneFrom: boundedIsoDate(params.get("milestone_from")),
          pipelineMilestoneTo: boundedIsoDate(params.get("milestone_to")),
          pipelineHasClinicalResults: (["true", "false"].includes(params.get("has_clinical_results") ?? "")
            ? (params.get("has_clinical_results") ?? "")
            : "") as "" | "true" | "false",
          pipelineClinicalResultEvaluation: trialResultEvaluations.has(params.get("clinical_result_evaluation") ?? "")
            ? (params.get("clinical_result_evaluation") ?? "")
            : "",
          pipelineHasDeal: (["true", "false"].includes(params.get("has_deal") ?? "")
            ? (params.get("has_deal") ?? "")
            : "") as "" | "true" | "false",
          pipelineDealCurrency: /^[A-Z]{3}$/.test(params.get("deal_currency") ?? "")
            ? (params.get("deal_currency") ?? "")
            : "",
          pipelineDealTotalPotentialAmountMin: boundedAmount(params.get("deal_total_potential_amount_min")),
          pipelineDealTotalPotentialAmountMax: boundedAmount(params.get("deal_total_potential_amount_max")),
          pipelineSort,
          pipelineSortBy: pipelineSort[0]?.field ?? "status_date",
          pipelineSortDirection: pipelineSort[0]?.direction ?? "desc",
          pipelineDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          pipelineResultGrain:
            view === "pipeline"
              ? pipelineResultGrains.has(params.get("result_grain") ?? "")
                ? (params.get("result_grain") as WorkspaceLocation["pipelineResultGrain"])
                : params.get("target_entity_id") && entityIdPattern.test(params.get("target_entity_id") ?? "")
                  ? ("drug" as const)
                  : ("program" as const)
              : undefined,
          ...(view === "target"
            ? {
                targetPipelineDisplayMode:
                  params.get("display") === "landscape"
                    ? ("landscape" as const)
                    : params.get("display") === "program"
                      ? ("program" as const)
                      : ("drug" as const),
              }
            : {}),
          pipelineAnalysisDimension: pipelineAnalysisDimensions.has(params.get("analysis_dimension") ?? "")
            ? (params.get("analysis_dimension") as WorkspaceLocation["pipelineAnalysisDimension"])
            : "all",
          pipelineAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          pipelineAnalysisLimit: pipelineAnalysisLimits.has(Number.parseInt(params.get("analysis_top") ?? "", 10))
            ? (Number.parseInt(params.get("analysis_top") ?? "", 10) as 5 | 8 | 20 | 50 | 100 | 200)
            : view === "target"
              ? 20
              : 8,
          pipelineAnalysisStageScope: pipelineAnalysisStageScopes.has(params.get("analysis_stage") ?? "")
            ? (params.get("analysis_stage") as WorkspaceLocation["pipelineAnalysisStageScope"])
            : "overall",
          pipelineTargetAggregation: pipelineTargetAggregations.has(params.get("target_aggregation") ?? "")
            ? (params.get("target_aggregation") as WorkspaceLocation["pipelineTargetAggregation"])
            : "all",
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawTrialId = view === "trials" ? params.get("trial") : null;
  const trialFilters =
    view === "trials"
      ? {
          registry: (params.get("registry") ?? "").trim().slice(0, 80),
          trialStatus: (params.get("status") ?? "").trim().slice(0, 100),
          trialPhase: (params.get("phase") ?? "").trim().slice(0, 80),
          studyType: (params.get("study_type") ?? "").trim().slice(0, 80),
          trialAcronym: (params.get("acronym") ?? "").trim().slice(0, 240),
          trialInitiationType: trialInitiationTypes.has(params.get("initiation_type") ?? "")
            ? (params.get("initiation_type") ?? "")
            : "",
          trialTherapyLine: trialTherapyLines.has(params.get("therapy_line") ?? "")
            ? (params.get("therapy_line") ?? "")
            : "",
          trialHasResults: ["true", "false"].includes(params.get("has_results") ?? "")
            ? (params.get("has_results") ?? "")
            : "",
          trialResultEvaluation: trialResultEvaluations.has(params.get("result_evaluation") ?? "")
            ? (params.get("result_evaluation") ?? "")
            : "",
          trialResultsPostedFrom: boundedIsoDate(params.get("results_posted_from")),
          trialResultsPostedTo: boundedIsoDate(params.get("results_posted_to")),
          trialInvestigationalDrug: (params.get("investigational_drug") ?? "").trim().slice(0, 500),
          trialCombinationDrug: (params.get("combination_drug") ?? "").trim().slice(0, 500),
          trialInvestigationalTarget: (params.get("investigational_target") ?? "").trim().slice(0, 500),
          trialCombinationTarget: (params.get("combination_target") ?? "").trim().slice(0, 500),
          trialInvestigationalDrugEntityIds: boundedRepeatedEntityIds(params, "investigational_drug_entity_ids"),
          trialCombinationDrugEntityIds: boundedRepeatedEntityIds(params, "combination_drug_entity_ids"),
          trialInvestigationalTargetEntityIds: boundedRepeatedEntityIds(params, "investigational_target_entity_ids"),
          trialCombinationTargetEntityIds: boundedRepeatedEntityIds(params, "combination_target_entity_ids"),
          trialLinkedDrugModalities: boundedRepeatedValues(params, "linked_drug_modality", 120),
          trialLinkedDrugInnovationTypes: boundedRepeatedValues(params, "linked_drug_innovation_type", 120),
          trialLinkedDrugCategories: boundedRepeatedValues(params, "linked_drug_category", 120),
          trialLinkedDrugProgramTags: boundedRepeatedValues(params, "linked_drug_program_tag", 240),
          trialLinkedDrugGlobalPhase: developmentPhases.has(params.get("linked_drug_global_phase") ?? "")
            ? (params.get("linked_drug_global_phase") ?? "")
            : "",
          trialLinkedDrugOrganizationCountryRegion: (params.get("linked_drug_organization_country_region") ?? "")
            .trim()
            .slice(0, 120),
          trialRoleEntityId:
            params.get("role_entity_id") && entityIdPattern.test(params.get("role_entity_id") ?? "")
              ? (params.get("role_entity_id") ?? "").toLowerCase()
              : "",
          trialRoleEntityIds: boundedRepeatedEntityIds(params, "role_entity_ids"),
          trialRoleEntityRole:
            ((params.get("role_entity_id") && entityIdPattern.test(params.get("role_entity_id") ?? "")) ||
              boundedRepeatedEntityIds(params, "role_entity_ids").length > 0) &&
            trialEntityRoles.has(params.get("role_entity_role") ?? "")
              ? (params.get("role_entity_role") ?? "")
              : "",
          trialHasKeyResult: ["true", "false"].includes(params.get("has_key_result") ?? "")
            ? (params.get("has_key_result") ?? "")
            : "",
          trialPublicationId: (params.get("publication_id") ?? "").trim().slice(0, 240),
          trialConference: (params.get("conference") ?? "").trim().slice(0, 500),
          trialDisclosedFrom: boundedIsoDate(params.get("disclosed_from")),
          trialDisclosedTo: boundedIsoDate(params.get("disclosed_to")),
          trialSort,
          trialSortBy: trialSort[0]?.field ?? "last_update_posted",
          trialSortDirection: trialSort[0]?.direction ?? "desc",
          trialDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          trialAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          trialId: rawTrialId && entityIdPattern.test(rawTrialId) ? rawTrialId.toLowerCase() : null,
          invalidTrialId: rawTrialId !== null && !entityIdPattern.test(rawTrialId),
          trialSection:
            rawTrialId && entityIdPattern.test(rawTrialId) && trialDossierSectionSet.has(requestedSection)
              ? (requestedSection as TrialDossierSection)
              : "overview",
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawPatentId = view === "patents" ? params.get("patent") : null;
  const patentFilters =
    view === "patents"
      ? {
          applicant: (params.get("applicant") ?? "").trim().slice(0, 300),
          patentEntityId:
            params.get("entity_id") && entityIdPattern.test(params.get("entity_id") ?? "")
              ? (params.get("entity_id") ?? "").toLowerCase()
              : "",
          patentPriorityFrom: boundedIsoDate(params.get("priority_from")),
          patentPriorityTo: boundedIsoDate(params.get("priority_to")),
          patentExpirationFrom: boundedIsoDate(params.get("expiration_from")),
          patentExpirationTo: boundedIsoDate(params.get("expiration_to")),
          legalStatus: (params.get("legal_status") ?? "").trim().slice(0, 120),
          patentDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          patentAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          patentSort,
          patentSortBy: patentSort[0]?.field ?? "priority_date",
          patentSortDirection: patentSort[0]?.direction ?? "desc",
          patentId: rawPatentId && entityIdPattern.test(rawPatentId) ? rawPatentId.toLowerCase() : null,
          invalidPatentId: rawPatentId !== null && !entityIdPattern.test(rawPatentId),
          patentSection:
            rawPatentId && entityIdPattern.test(rawPatentId) && patentDossierSectionSet.has(params.get("section") ?? "")
              ? ((params.get("section") ?? "overview") as PatentDossierSection)
              : "overview",
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawDealId = view === "deals" ? params.get("deal") : null;
  const dealFilters =
    view === "deals"
      ? {
          dealType: (params.get("deal_type") ?? "").trim().slice(0, 100),
          dealStatus: dealStatuses.has(params.get("status") ?? "") ? (params.get("status") ?? "") : "",
          dealDirection: dealDirections.has(params.get("direction") ?? "") ? (params.get("direction") ?? "") : "",
          dealDirectionReferenceJurisdiction: (params.get("direction_reference_jurisdiction") ?? "")
            .trim()
            .slice(0, 120),
          dealTerritory: (params.get("territory") ?? "").trim().slice(0, 240),
          dealAssetEntityId:
            params.get("asset_entity_id") && entityIdPattern.test(params.get("asset_entity_id") ?? "")
              ? (params.get("asset_entity_id") ?? "").toLowerCase()
              : "",
          dealTargetEntityId:
            params.get("target_entity_id") && entityIdPattern.test(params.get("target_entity_id") ?? "")
              ? (params.get("target_entity_id") ?? "").toLowerCase()
              : "",
          dealDiseaseEntityId:
            params.get("disease_entity_id") && entityIdPattern.test(params.get("disease_entity_id") ?? "")
              ? (params.get("disease_entity_id") ?? "").toLowerCase()
              : "",
          dealAssetModalities: boundedRepeatedValues(params, "asset_modality", 120),
          dealAssetProgramTags: boundedRepeatedValues(params, "asset_program_tag", 240),
          dealParty: (params.get("party") ?? "").trim().slice(0, 500),
          dealPartyEntityId:
            params.get("party_entity_id") && entityIdPattern.test(params.get("party_entity_id") ?? "")
              ? (params.get("party_entity_id") ?? "").toLowerCase()
              : "",
          dealPartyRole: dealPartyRoles.has(params.get("party_role") ?? "") ? (params.get("party_role") ?? "") : "",
          dealPartyCountryRegion: (params.get("party_country_region") ?? "").trim().slice(0, 120),
          dealPartyOrganizationType: (params.get("party_organization_type") ?? "").trim().slice(0, 120),
          dealDevelopmentPhaseAtTransaction: developmentPhases.has(params.get("development_phase_at_transaction") ?? "")
            ? (params.get("development_phase_at_transaction") ?? "")
            : "",
          dealCurrentDevelopmentPhase: developmentPhases.has(params.get("current_development_phase") ?? "")
            ? (params.get("current_development_phase") ?? "")
            : "",
          dealRightType: dealRightTypes.has(params.get("right_type") ?? "") ? (params.get("right_type") ?? "") : "",
          dealRightsTerritory: (params.get("rights_territory") ?? "").trim().slice(0, 240),
          dealCurrency: /^[A-Z]{3}$/.test(params.get("currency") ?? "") ? (params.get("currency") ?? "") : "",
          dealAnnouncedFrom: boundedIsoDate(params.get("announced_from")),
          dealAnnouncedTo: boundedIsoDate(params.get("announced_to")),
          dealTerminatedFrom: boundedIsoDate(params.get("terminated_from")),
          dealTerminatedTo: boundedIsoDate(params.get("terminated_to")),
          dealSourceUpdatedFrom: boundedIsoDate(params.get("source_updated_from")),
          dealSourceUpdatedTo: boundedIsoDate(params.get("source_updated_to")),
          dealUpfrontAmountMin: boundedAmount(params.get("upfront_amount_min")),
          dealUpfrontAmountMax: boundedAmount(params.get("upfront_amount_max")),
          dealTotalPotentialAmountMin: boundedAmount(params.get("total_potential_amount_min")),
          dealTotalPotentialAmountMax: boundedAmount(params.get("total_potential_amount_max")),
          dealSort,
          dealSortBy: dealSort[0]?.field ?? "announced_at",
          dealSortDirection: dealSort[0]?.direction ?? "desc",
          dealDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          dealAnalysisDimension: dealAnalysisDimensions.has(params.get("analysis_dimension") ?? "")
            ? (params.get("analysis_dimension") as WorkspaceLocation["dealAnalysisDimension"])
            : "all",
          dealAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          dealAnalysisLimit: dealAnalysisLimits.has(Number.parseInt(params.get("analysis_top") ?? "", 10))
            ? (Number.parseInt(params.get("analysis_top") ?? "", 10) as 5 | 8 | 20 | 50)
            : 8,
          dealId: rawDealId && entityIdPattern.test(rawDealId) ? rawDealId.toLowerCase() : null,
          invalidDealId: rawDealId !== null && !entityIdPattern.test(rawDealId),
          dealSection:
            rawDealId && entityIdPattern.test(rawDealId) && dealDossierSectionSet.has(params.get("section") ?? "")
              ? ((params.get("section") ?? "overview") as DealDossierSection)
              : "overview",
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawRegulatoryEventId = view === "regulatory" ? params.get("regulatory_event") : null;
  const regulatoryFilters =
    view === "regulatory"
      ? {
          regulatoryAgency: (params.get("agency") ?? "").trim().slice(0, 80),
          regulatoryJurisdiction: (params.get("jurisdiction") ?? "").trim().slice(0, 120),
          regulatoryEventType: (params.get("event_type") ?? "").trim().slice(0, 40),
          regulatoryStatus: (params.get("status") ?? "").trim().slice(0, 120),
          regulatoryDesignationType: regulatoryDesignationTypes.has(params.get("designation_type") ?? "")
            ? (params.get("designation_type") ?? "")
            : "",
          regulatoryLabelChangeType: regulatoryLabelChangeTypes.has(params.get("label_change_type") ?? "")
            ? (params.get("label_change_type") ?? "")
            : "",
          regulatoryBoxedWarning: ["true", "false"].includes(params.get("boxed_warning") ?? "")
            ? (params.get("boxed_warning") ?? "")
            : "",
          regulatorySafetySignalType: regulatorySafetySignalTypes.has(params.get("safety_signal_type") ?? "")
            ? (params.get("safety_signal_type") ?? "")
            : "",
          regulatorySafetySeverity: regulatorySafetySeverities.has(params.get("safety_severity") ?? "")
            ? (params.get("safety_severity") ?? "")
            : "",
          regulatorySafetyStatus: regulatorySafetyStatuses.has(params.get("safety_status") ?? "")
            ? (params.get("safety_status") ?? "")
            : "",
          regulatoryDecisionFrom: boundedIsoDate(params.get("decision_from")),
          regulatoryDecisionTo: boundedIsoDate(params.get("decision_to")),
          regulatorySourceUpdatedFrom: boundedIsoDate(params.get("source_updated_from")),
          regulatorySourceUpdatedTo: boundedIsoDate(params.get("source_updated_to")),
          regulatoryDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          regulatoryAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          regulatorySort,
          regulatorySortBy: regulatorySort[0]?.field ?? "decision_date",
          regulatorySortDirection: regulatorySort[0]?.direction ?? "desc",
          regulatoryEventId:
            rawRegulatoryEventId && entityIdPattern.test(rawRegulatoryEventId)
              ? rawRegulatoryEventId.toLowerCase()
              : null,
          invalidRegulatoryEventId: rawRegulatoryEventId !== null && !entityIdPattern.test(rawRegulatoryEventId),
          regulatoryCompareIds: boundedEntityIdList(params.get("compare")),
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const epidemiologyFilters =
    view === "epidemiology"
      ? {
          epidemiologyDiseaseEntityId:
            params.get("disease_entity_id") && entityIdPattern.test(params.get("disease_entity_id") ?? "")
              ? (params.get("disease_entity_id") ?? "").toLowerCase()
              : "",
          epidemiologyDisplayMode: params.get("display") === "landscape" ? ("landscape" as const) : ("list" as const),
          epidemiologyAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          epidemiologyMeasure: (params.get("measure") ?? "").trim().slice(0, 40),
          epidemiologyGeography: (params.get("geography") ?? "").trim().slice(0, 160),
          epidemiologyUnit: (params.get("unit") ?? "").trim().slice(0, 120),
          epidemiologyPatientPopulationId:
            params.get("patient_population_id") && entityIdPattern.test(params.get("patient_population_id") ?? "")
              ? (params.get("patient_population_id") ?? "").toLowerCase()
              : "",
          epidemiologyPopulationScope: (params.get("population_scope") ?? "").trim().slice(0, 500),
          epidemiologyAgeGroup: (params.get("age_group") ?? "").trim().slice(0, 120),
          epidemiologySex: (params.get("sex") ?? "").trim().slice(0, 80),
          epidemiologyPeriodStartFrom: boundedIsoDate(params.get("period_start_from")),
          epidemiologyPeriodEndTo: boundedIsoDate(params.get("period_end_to")),
          epidemiologySort,
          epidemiologySortBy: epidemiologySort[0]?.field ?? "period_end",
          epidemiologySortDirection: epidemiologySort[0]?.direction ?? "desc",
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawNewsEventId = view === "news" ? params.get("news_event") : null;
  const newsFilters =
    view === "news"
      ? {
          newsEventType: (params.get("event_type") ?? "").trim().slice(0, 40),
          newsPublisher: (params.get("publisher") ?? "").trim().slice(0, 300),
          newsLanguage: (params.get("language") ?? "").trim().slice(0, 40),
          newsVenue: (params.get("venue") ?? "").trim().slice(0, 240),
          newsPublishedFrom: boundedIsoDate(params.get("published_from")),
          newsPublishedTo: boundedIsoDate(params.get("published_to")),
          newsContentScope: params.get("content_scope") === "research" ? ("research" as const) : ("" as const),
          newsEntityId:
            params.get("entity_id") && entityIdPattern.test(params.get("entity_id") ?? "")
              ? (params.get("entity_id") ?? "").toLowerCase()
              : "",
          newsDisplayMode:
            params.get("display") === "timeline"
              ? ("timeline" as const)
              : params.get("display") === "landscape"
                ? ("landscape" as const)
                : ("list" as const),
          newsAnalysisView: params.get("analysis_view") === "table" ? ("table" as const) : ("chart" as const),
          newsSort,
          newsSortBy: newsSort[0]?.field ?? "published_at",
          newsSortDirection: newsSort[0]?.direction ?? "desc",
          newsEventId: rawNewsEventId && entityIdPattern.test(rawNewsEventId) ? rawNewsEventId.toLowerCase() : null,
          invalidNewsEventId: rawNewsEventId !== null && !entityIdPattern.test(rawNewsEventId),
          offset: Math.min(100_000, Math.max(0, Number.parseInt(params.get("offset") ?? "0", 10) || 0)),
        }
      : {};
  const rawKnowledgePageId = view === "knowledge" ? params.get("page") : null;
  const knowledgePageId =
    rawKnowledgePageId && entityIdPattern.test(rawKnowledgePageId) ? rawKnowledgePageId.toLowerCase() : null;
  const requestedKnowledgePanel = params.get("panel");
  const knowledgePanel: KnowledgePanel =
    knowledgePageId && (requestedKnowledgePanel === "coverage" || requestedKnowledgePanel === "governance")
      ? "coverage"
      : "document";
  const requestedKnowledgeVersion = Number.parseInt(params.get("version") ?? "", 10);
  const knowledgeFilters =
    view === "knowledge"
      ? {
          knowledgePageId,
          invalidKnowledgePageId: rawKnowledgePageId !== null && knowledgePageId === null,
          knowledgePanel,
          knowledgeVersionNumber:
            knowledgePanel === "coverage" &&
            Number.isSafeInteger(requestedKnowledgeVersion) &&
            requestedKnowledgeVersion > 0 &&
            requestedKnowledgeVersion <= 1_000_000
              ? requestedKnowledgeVersion
              : null,
        }
      : {};
  const evidenceQuery = view === "evidence" && query.length >= 2 ? query : "";
  const requestedEvidenceDocumentId = view === "evidence" ? params.get("document") : null;
  const evidenceDocumentId = evidenceQuery ? boundedEvidenceDocumentId(requestedEvidenceDocumentId) : null;
  const requestedEvidenceChunk = Number.parseInt(params.get("chunk") ?? "", 10);
  const evidenceFilters =
    view === "evidence"
      ? {
          evidenceDatasetKeys: evidenceQuery ? boundedRepeatedValues(params, "dataset", 120).sort() : [],
          evidenceDocumentId,
          evidenceChunkIndex:
            evidenceDocumentId &&
            Number.isSafeInteger(requestedEvidenceChunk) &&
            requestedEvidenceChunk > 0 &&
            requestedEvidenceChunk <= 20
              ? requestedEvidenceChunk - 1
              : null,
        }
      : {};
  const rawCollectionId = view === "collections" ? params.get("collection") : null;
  const collectionId = rawCollectionId && entityIdPattern.test(rawCollectionId) ? rawCollectionId.toLowerCase() : null;
  const collectionFilters =
    view === "collections"
      ? {
          collectionId,
          invalidCollectionId: rawCollectionId !== null && collectionId === null,
          collectionCompareEntityIds: collectionId ? boundedEntityIdList(params.get("compare")) : [],
        }
      : {};
  const monitoringFilters =
    view === "monitoring"
      ? {
          monitoringTab: monitoringTabSet.has(params.get("monitor_tab") ?? "")
            ? (params.get("monitor_tab") as MonitoringTab)
            : ("alerts" as const),
        }
      : {};
  return {
    workbench,
    view,
    query: view === "evidence" ? evidenceQuery : query,
    entityType,
    reviewStatus,
    entityId,
    invalidEntityId: rawEntityId !== null && entityId === null,
    ...(returnTo ? { returnTo } : {}),
    ...chemistryFilters,
    ...dossierSection,
    ...explorerFilters,
    ...pipelineFilters,
    ...trialFilters,
    ...patentFilters,
    ...dealFilters,
    ...regulatoryFilters,
    ...epidemiologyFilters,
    ...newsFilters,
    ...knowledgeFilters,
    ...evidenceFilters,
    ...collectionFilters,
    ...monitoringFilters,
  };
}

export function workspaceUrl(
  location: Pick<
    WorkspaceLocation,
    | "workbench"
    | "view"
    | "query"
    | "entityType"
    | "entityTypes"
    | "reviewStatus"
    | "entitySort"
    | "entitySortBy"
    | "entitySortDirection"
    | "explorerDisplayMode"
    | "explorerAnalysisView"
    | "entityId"
    | "returnTo"
    | "chemistrySavedSearchId"
    | "knowledgePageId"
    | "knowledgePanel"
    | "knowledgeVersionNumber"
    | "monitoringTab"
    | "evidenceDatasetKeys"
    | "evidenceDocumentId"
    | "evidenceChunkIndex"
    | "targetSection"
    | "drugSection"
    | "companySection"
    | "diseaseSection"
    | "entitySection"
    | "pipelineModalities"
    | "pipelineInnovationTypes"
    | "pipelineTherapeuticAreas"
    | "pipelineDrugCategories"
    | "pipelineProgramStatus"
    | "pipelineOrganizationRole"
    | "pipelineOrganizationType"
    | "pipelineOrganizationCountryRegion"
    | "phase"
    | "geography"
    | "pipelineStatusDateFrom"
    | "pipelineStatusDateTo"
    | "pipelineDrugEntityId"
    | "pipelineTargetEntityId"
    | "pipelineTargetCombinationKey"
    | "pipelineDiseaseEntityId"
    | "pipelineOrganizationEntityId"
    | "pipelineGlobalPhase"
    | "pipelineChinaPhase"
    | "pipelineGlobalPhaseStartedFrom"
    | "pipelineGlobalPhaseStartedTo"
    | "pipelineChinaPhaseStartedFrom"
    | "pipelineChinaPhaseStartedTo"
    | "pipelineDevelopmentRightsRegion"
    | "pipelineCommercializationRightsRegion"
    | "pipelineProgramTags"
    | "pipelineMilestoneType"
    | "pipelineMilestoneFrom"
    | "pipelineMilestoneTo"
    | "pipelineHasClinicalResults"
    | "pipelineClinicalResultEvaluation"
    | "pipelineHasDeal"
    | "pipelineDealCurrency"
    | "pipelineDealTotalPotentialAmountMin"
    | "pipelineDealTotalPotentialAmountMax"
    | "pipelineSort"
    | "pipelineSortBy"
    | "pipelineSortDirection"
    | "pipelineDisplayMode"
    | "pipelineResultGrain"
    | "targetPipelineDisplayMode"
    | "pipelineAnalysisDimension"
    | "pipelineAnalysisView"
    | "pipelineAnalysisLimit"
    | "pipelineAnalysisStageScope"
    | "pipelineTargetAggregation"
    | "registry"
    | "trialStatus"
    | "trialPhase"
    | "studyType"
    | "trialAcronym"
    | "trialInitiationType"
    | "trialTherapyLine"
    | "trialHasResults"
    | "trialResultEvaluation"
    | "trialResultsPostedFrom"
    | "trialResultsPostedTo"
    | "trialInvestigationalDrug"
    | "trialCombinationDrug"
    | "trialInvestigationalTarget"
    | "trialCombinationTarget"
    | "trialInvestigationalDrugEntityIds"
    | "trialCombinationDrugEntityIds"
    | "trialInvestigationalTargetEntityIds"
    | "trialCombinationTargetEntityIds"
    | "trialLinkedDrugModalities"
    | "trialLinkedDrugInnovationTypes"
    | "trialLinkedDrugCategories"
    | "trialLinkedDrugProgramTags"
    | "trialLinkedDrugGlobalPhase"
    | "trialLinkedDrugOrganizationCountryRegion"
    | "trialRoleEntityId"
    | "trialRoleEntityIds"
    | "trialRoleEntityRole"
    | "trialHasKeyResult"
    | "trialPublicationId"
    | "trialConference"
    | "trialDisclosedFrom"
    | "trialDisclosedTo"
    | "trialSort"
    | "trialSortBy"
    | "trialSortDirection"
    | "trialDisplayMode"
    | "trialAnalysisView"
    | "trialId"
    | "trialSection"
    | "applicant"
    | "legalStatus"
    | "patentSort"
    | "patentSortBy"
    | "patentEntityId"
    | "patentPriorityFrom"
    | "patentPriorityTo"
    | "patentExpirationFrom"
    | "patentExpirationTo"
    | "patentDisplayMode"
    | "patentAnalysisView"
    | "regulatoryDisplayMode"
    | "regulatoryAnalysisView"
    | "patentSortDirection"
    | "patentId"
    | "patentSection"
    | "dealType"
    | "dealStatus"
    | "dealDirection"
    | "dealDirectionReferenceJurisdiction"
    | "dealTerritory"
    | "dealAssetEntityId"
    | "dealTargetEntityId"
    | "dealDiseaseEntityId"
    | "dealAssetModalities"
    | "dealAssetProgramTags"
    | "dealParty"
    | "dealPartyEntityId"
    | "dealPartyRole"
    | "dealPartyCountryRegion"
    | "dealPartyOrganizationType"
    | "dealDevelopmentPhaseAtTransaction"
    | "dealCurrentDevelopmentPhase"
    | "dealRightType"
    | "dealRightsTerritory"
    | "dealCurrency"
    | "dealAnnouncedFrom"
    | "dealAnnouncedTo"
    | "dealTerminatedFrom"
    | "dealTerminatedTo"
    | "dealSourceUpdatedFrom"
    | "dealSourceUpdatedTo"
    | "dealUpfrontAmountMin"
    | "dealUpfrontAmountMax"
    | "dealTotalPotentialAmountMin"
    | "dealTotalPotentialAmountMax"
    | "dealSort"
    | "dealSortBy"
    | "dealSortDirection"
    | "dealDisplayMode"
    | "dealAnalysisDimension"
    | "dealAnalysisView"
    | "dealAnalysisLimit"
    | "dealId"
    | "dealSection"
    | "regulatoryAgency"
    | "regulatoryJurisdiction"
    | "regulatoryEventType"
    | "regulatoryStatus"
    | "regulatoryDesignationType"
    | "regulatoryLabelChangeType"
    | "regulatoryBoxedWarning"
    | "regulatorySafetySignalType"
    | "regulatorySafetySeverity"
    | "regulatorySafetyStatus"
    | "regulatoryDecisionFrom"
    | "regulatoryDecisionTo"
    | "regulatorySourceUpdatedFrom"
    | "regulatorySourceUpdatedTo"
    | "regulatorySort"
    | "regulatorySortBy"
    | "regulatorySortDirection"
    | "regulatoryEventId"
    | "regulatoryCompareIds"
    | "epidemiologyMeasure"
    | "epidemiologyDiseaseEntityId"
    | "epidemiologyGeography"
    | "epidemiologyUnit"
    | "epidemiologyPatientPopulationId"
    | "epidemiologyPopulationScope"
    | "epidemiologyAgeGroup"
    | "epidemiologySex"
    | "epidemiologyPeriodStartFrom"
    | "epidemiologyPeriodEndTo"
    | "epidemiologySort"
    | "epidemiologySortBy"
    | "epidemiologySortDirection"
    | "newsEventType"
    | "newsPublisher"
    | "newsLanguage"
    | "newsVenue"
    | "newsPublishedFrom"
    | "newsPublishedTo"
    | "newsContentScope"
    | "newsEntityId"
    | "newsDisplayMode"
    | "newsAnalysisView"
    | "epidemiologyDisplayMode"
    | "epidemiologyAnalysisView"
    | "newsSort"
    | "newsSortBy"
    | "newsSortDirection"
    | "newsEventId"
    | "collectionId"
    | "collectionCompareEntityIds"
    | "offset"
  >,
): string {
  const params = new URLSearchParams();
  if (
    location.view !== workbenchDefaults[location.workbench] ||
    (location.workbench === "research" && location.view === "explorer")
  ) {
    params.set("view", location.view);
  }
  if (
    (location.view === "explorer" ||
      location.view === "target" ||
      location.view === "drug" ||
      location.view === "company" ||
      location.view === "disease" ||
      location.view === "entity") &&
    location.query.trim()
  ) {
    params.set("q", location.query.trim().slice(0, 500));
  }
  if (location.view === "pipeline" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "trials" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "patents" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "deals" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "regulatory" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "epidemiology" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "news" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "knowledge" && location.query.trim()) params.set("q", location.query.trim().slice(0, 500));
  if (location.view === "evidence" && location.query.trim().length >= 2) {
    params.set("q", location.query.trim().slice(0, 500));
    for (const key of Array.from(new Set(location.evidenceDatasetKeys ?? [])).sort()) {
      if (key.trim() && key.length <= 120) params.append("dataset", key.trim());
    }
    if (
      location.evidenceDocumentId &&
      boundedEvidenceDocumentId(location.evidenceDocumentId) &&
      location.evidenceChunkIndex !== null &&
      location.evidenceChunkIndex !== undefined &&
      Number.isSafeInteger(location.evidenceChunkIndex) &&
      location.evidenceChunkIndex >= 0 &&
      location.evidenceChunkIndex < 20
    ) {
      params.set("document", location.evidenceDocumentId.trim());
      params.set("chunk", String(location.evidenceChunkIndex + 1));
    }
  }
  if (location.view === "knowledge" && location.knowledgePageId && entityIdPattern.test(location.knowledgePageId)) {
    params.set("page", location.knowledgePageId.toLowerCase());
    if (location.knowledgePanel === "coverage") {
      params.set("panel", "coverage");
      if (
        location.knowledgeVersionNumber &&
        Number.isSafeInteger(location.knowledgeVersionNumber) &&
        location.knowledgeVersionNumber > 0 &&
        location.knowledgeVersionNumber <= 1_000_000
      ) {
        params.set("version", String(location.knowledgeVersionNumber));
      }
    }
  }
  if (location.view === "monitoring" && location.monitoringTab && location.monitoringTab !== "alerts") {
    if (monitoringTabSet.has(location.monitoringTab)) params.set("monitor_tab", location.monitoringTab);
  }
  if (
    location.view === "chemistry" &&
    location.chemistrySavedSearchId &&
    entityIdPattern.test(location.chemistrySavedSearchId)
  ) {
    params.set("saved", location.chemistrySavedSearchId.toLowerCase());
  }
  if (location.view === "explorer") {
    const selectedEntityTypes = Array.from(
      new Set(
        (location.entityTypes?.length ? location.entityTypes : [location.entityType]).filter((value) =>
          entityTypes.has(value),
        ),
      ),
    ).sort(
      (left, right) =>
        entityTypeValues.indexOf(left as (typeof entityTypeValues)[number]) -
        entityTypeValues.indexOf(right as (typeof entityTypeValues)[number]),
    );
    if (selectedEntityTypes.length === 1) params.set("type", selectedEntityTypes[0] ?? "");
    if (selectedEntityTypes.length > 1) params.set("types", selectedEntityTypes.slice(0, 10).join(","));
  }
  if (location.view === "explorer" && reviewStatuses.has(location.reviewStatus)) {
    params.set("review", location.reviewStatus);
  }
  if (location.view === "explorer") {
    appendLocationSort(
      params,
      location.entitySort,
      entitySortFields,
      location.entitySortBy,
      location.entitySortDirection,
      "relevance",
    );
    if (location.explorerDisplayMode === "landscape") {
      params.set("display", "landscape");
      if (location.explorerAnalysisView === "table") params.set("analysis_view", "table");
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (
    (location.view === "explorer" ||
      location.view === "target" ||
      location.view === "drug" ||
      location.view === "company" ||
      location.view === "disease" ||
      location.view === "entity") &&
    location.entityId
  ) {
    params.set("entity", location.entityId);
  }
  if (location.workbench === "research") {
    const returnTo = boundedResearchReturnPath(location.returnTo);
    if (returnTo) params.set("from", returnTo);
  }
  if (
    location.view === "target" &&
    location.targetSection &&
    location.targetSection !== "overview" &&
    targetDossierSectionSet.has(location.targetSection)
  ) {
    params.set("section", location.targetSection);
  }
  if (
    location.view === "drug" &&
    location.drugSection &&
    location.drugSection !== "overview" &&
    drugDossierSectionSet.has(location.drugSection)
  ) {
    params.set("section", location.drugSection);
  }
  if (location.view === "drug" && location.drugSection === "pipeline" && location.offset && location.offset > 0) {
    params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (
    location.view === "company" &&
    location.companySection &&
    location.companySection !== "overview" &&
    companyDossierSectionSet.has(location.companySection)
  ) {
    params.set("section", location.companySection);
  }
  if (
    location.view === "disease" &&
    location.diseaseSection &&
    location.diseaseSection !== "overview" &&
    diseaseDossierSectionSet.has(location.diseaseSection)
  ) {
    params.set("section", location.diseaseSection);
  }
  if (
    location.view === "entity" &&
    location.entitySection &&
    location.entitySection !== "overview" &&
    entityDossierSectionSet.has(location.entitySection)
  ) {
    params.set("section", location.entitySection);
  }
  if (location.view === "pipeline" || (location.view === "target" && location.targetSection === "pipeline")) {
    for (const value of location.pipelineModalities ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 120) params.append("modality", normalized);
    }
    for (const value of location.pipelineInnovationTypes ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 120) params.append("innovation_type", normalized);
    }
    for (const value of location.pipelineTherapeuticAreas ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 120) params.append("therapeutic_area", normalized);
    }
    for (const value of location.pipelineDrugCategories ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 120) params.append("drug_category", normalized);
    }
    if (["active", "inactive", "unknown", "all"].includes(location.pipelineProgramStatus ?? "")) {
      params.set("program_status", location.pipelineProgramStatus ?? "");
    }
    if (pipelineOrganizationRoles.has(location.pipelineOrganizationRole ?? "")) {
      params.set("organization_role", location.pipelineOrganizationRole ?? "");
    }
    if (location.pipelineOrganizationType?.trim()) {
      params.set("organization_type", location.pipelineOrganizationType.trim().slice(0, 120));
    }
    if (location.pipelineOrganizationCountryRegion?.trim()) {
      params.set("organization_country_region", location.pipelineOrganizationCountryRegion.trim().slice(0, 120));
    }
    if (location.phase && developmentPhases.has(location.phase)) params.set("phase", location.phase);
    if (location.geography?.trim()) params.set("geography", location.geography.trim().slice(0, 120));
    if (boundedIsoDate(location.pipelineStatusDateFrom ?? "")) {
      params.set("status_date_from", location.pipelineStatusDateFrom ?? "");
    }
    if (boundedIsoDate(location.pipelineStatusDateTo ?? "")) {
      params.set("status_date_to", location.pipelineStatusDateTo ?? "");
    }
    if (location.pipelineDrugEntityId && entityIdPattern.test(location.pipelineDrugEntityId)) {
      params.set("drug_entity_id", location.pipelineDrugEntityId.toLowerCase());
    }
    if (location.pipelineTargetEntityId && entityIdPattern.test(location.pipelineTargetEntityId)) {
      params.set("target_entity_id", location.pipelineTargetEntityId.toLowerCase());
    }
    const targetCombinationKey = boundedTargetCombinationKey(location.pipelineTargetCombinationKey);
    if (targetCombinationKey) params.set("target_combination_key", targetCombinationKey);
    if (location.pipelineDiseaseEntityId && entityIdPattern.test(location.pipelineDiseaseEntityId)) {
      params.set("disease_entity_id", location.pipelineDiseaseEntityId.toLowerCase());
    }
    if (location.pipelineOrganizationEntityId && entityIdPattern.test(location.pipelineOrganizationEntityId)) {
      params.set("organization_entity_id", location.pipelineOrganizationEntityId.toLowerCase());
    }
    if (developmentPhases.has(location.pipelineGlobalPhase ?? "")) {
      params.set("global_phase", location.pipelineGlobalPhase ?? "");
    }
    if (developmentPhases.has(location.pipelineChinaPhase ?? "")) {
      params.set("china_phase", location.pipelineChinaPhase ?? "");
    }
    if (boundedIsoDate(location.pipelineGlobalPhaseStartedFrom ?? "")) {
      params.set("global_phase_started_from", location.pipelineGlobalPhaseStartedFrom ?? "");
    }
    if (boundedIsoDate(location.pipelineGlobalPhaseStartedTo ?? "")) {
      params.set("global_phase_started_to", location.pipelineGlobalPhaseStartedTo ?? "");
    }
    if (boundedIsoDate(location.pipelineChinaPhaseStartedFrom ?? "")) {
      params.set("china_phase_started_from", location.pipelineChinaPhaseStartedFrom ?? "");
    }
    if (boundedIsoDate(location.pipelineChinaPhaseStartedTo ?? "")) {
      params.set("china_phase_started_to", location.pipelineChinaPhaseStartedTo ?? "");
    }
    if (location.pipelineDevelopmentRightsRegion?.trim()) {
      params.set("development_rights_region", location.pipelineDevelopmentRightsRegion.trim().slice(0, 240));
    }
    if (location.pipelineCommercializationRightsRegion?.trim()) {
      params.set(
        "commercialization_rights_region",
        location.pipelineCommercializationRightsRegion.trim().slice(0, 240),
      );
    }
    for (const value of location.pipelineProgramTags ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 240) params.append("program_tag", normalized);
    }
    if (location.pipelineMilestoneType?.trim()) {
      params.set("milestone_type", location.pipelineMilestoneType.trim().slice(0, 120));
    }
    const pipelineMilestoneFrom = boundedIsoDate(location.pipelineMilestoneFrom ?? null);
    if (pipelineMilestoneFrom) {
      params.set("milestone_from", pipelineMilestoneFrom);
    }
    const pipelineMilestoneTo = boundedIsoDate(location.pipelineMilestoneTo ?? null);
    if (pipelineMilestoneTo) {
      params.set("milestone_to", pipelineMilestoneTo);
    }
    if (location.pipelineHasClinicalResults === "true" || location.pipelineHasClinicalResults === "false") {
      params.set("has_clinical_results", location.pipelineHasClinicalResults);
    }
    if (
      location.pipelineClinicalResultEvaluation &&
      trialResultEvaluations.has(location.pipelineClinicalResultEvaluation)
    ) {
      params.set("clinical_result_evaluation", location.pipelineClinicalResultEvaluation);
    }
    if (location.pipelineHasDeal === "true" || location.pipelineHasDeal === "false") {
      params.set("has_deal", location.pipelineHasDeal);
    }
    if (/^[A-Z]{3}$/.test(location.pipelineDealCurrency ?? "")) {
      params.set("deal_currency", location.pipelineDealCurrency ?? "");
    }
    for (const [key, value] of [
      ["deal_total_potential_amount_min", location.pipelineDealTotalPotentialAmountMin],
      ["deal_total_potential_amount_max", location.pipelineDealTotalPotentialAmountMax],
    ] as const) {
      if (boundedAmount(value ?? "")) params.set(key, value ?? "");
    }
    appendLocationSort(
      params,
      location.pipelineSort,
      pipelineSortFields,
      location.pipelineSortBy,
      location.pipelineSortDirection,
      "status_date",
    );
    if (location.view === "target" && location.targetSection === "pipeline") {
      if (location.targetPipelineDisplayMode === "landscape" || location.targetPipelineDisplayMode === "program") {
        params.set("display", location.targetPipelineDisplayMode);
      }
    } else if (location.pipelineDisplayMode === "landscape") {
      params.set("display", "landscape");
    }
    if (location.view === "pipeline") {
      const defaultResultGrain = location.pipelineTargetEntityId ? "drug" : "program";
      if (location.pipelineResultGrain && location.pipelineResultGrain !== defaultResultGrain) {
        params.set("result_grain", location.pipelineResultGrain);
      }
    }
    if (
      location.pipelineAnalysisDimension &&
      location.pipelineAnalysisDimension !== "all" &&
      pipelineAnalysisDimensions.has(location.pipelineAnalysisDimension)
    ) {
      params.set("analysis_dimension", location.pipelineAnalysisDimension);
    }
    if (location.pipelineAnalysisView === "table") {
      params.set("analysis_view", "table");
    }
    const defaultPipelineAnalysisLimit = location.view === "target" && location.targetSection === "pipeline" ? 20 : 8;
    if (location.pipelineAnalysisLimit && location.pipelineAnalysisLimit !== defaultPipelineAnalysisLimit) {
      params.set("analysis_top", String(location.pipelineAnalysisLimit));
    }
    if (location.pipelineAnalysisStageScope && location.pipelineAnalysisStageScope !== "overall") {
      params.set("analysis_stage", location.pipelineAnalysisStageScope);
    }
    if (location.pipelineTargetAggregation === "primary") {
      params.set("target_aggregation", "primary");
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "trials") {
    if (location.registry?.trim()) params.set("registry", location.registry.trim().slice(0, 80));
    if (location.trialStatus?.trim()) params.set("status", location.trialStatus.trim().slice(0, 100));
    if (location.trialPhase?.trim()) params.set("phase", location.trialPhase.trim().slice(0, 80));
    if (location.studyType?.trim()) params.set("study_type", location.studyType.trim().slice(0, 80));
    if (location.trialAcronym?.trim()) params.set("acronym", location.trialAcronym.trim().slice(0, 240));
    if (trialInitiationTypes.has(location.trialInitiationType ?? "")) {
      params.set("initiation_type", location.trialInitiationType ?? "");
    }
    if (trialTherapyLines.has(location.trialTherapyLine ?? "")) {
      params.set("therapy_line", location.trialTherapyLine ?? "");
    }
    if (["true", "false"].includes(location.trialHasResults ?? "")) {
      params.set("has_results", location.trialHasResults ?? "");
    }
    if (trialResultEvaluations.has(location.trialResultEvaluation ?? "")) {
      params.set("result_evaluation", location.trialResultEvaluation ?? "");
    }
    if (boundedIsoDate(location.trialResultsPostedFrom ?? "")) {
      params.set("results_posted_from", location.trialResultsPostedFrom ?? "");
    }
    if (boundedIsoDate(location.trialResultsPostedTo ?? "")) {
      params.set("results_posted_to", location.trialResultsPostedTo ?? "");
    }
    if (location.trialInvestigationalDrug?.trim()) {
      params.set("investigational_drug", location.trialInvestigationalDrug.trim().slice(0, 500));
    }
    if (location.trialCombinationDrug?.trim()) {
      params.set("combination_drug", location.trialCombinationDrug.trim().slice(0, 500));
    }
    if (location.trialInvestigationalTarget?.trim()) {
      params.set("investigational_target", location.trialInvestigationalTarget.trim().slice(0, 500));
    }
    if (location.trialCombinationTarget?.trim()) {
      params.set("combination_target", location.trialCombinationTarget.trim().slice(0, 500));
    }
    for (const [field, values] of [
      ["investigational_drug_entity_ids", location.trialInvestigationalDrugEntityIds],
      ["combination_drug_entity_ids", location.trialCombinationDrugEntityIds],
      ["investigational_target_entity_ids", location.trialInvestigationalTargetEntityIds],
      ["combination_target_entity_ids", location.trialCombinationTargetEntityIds],
    ] as const) {
      const entityIds = Array.from(new Set((values ?? []).map((entityId) => entityId.toLowerCase())))
        .filter((entityId) => entityIdPattern.test(entityId))
        .sort()
        .slice(0, 20);
      for (const entityId of entityIds) params.append(field, entityId);
    }
    for (const [field, values, maxLength] of [
      ["linked_drug_modality", location.trialLinkedDrugModalities, 120],
      ["linked_drug_innovation_type", location.trialLinkedDrugInnovationTypes, 120],
      ["linked_drug_category", location.trialLinkedDrugCategories, 120],
      ["linked_drug_program_tag", location.trialLinkedDrugProgramTags, 240],
    ] as const) {
      const normalizedValues = Array.from(new Set((values ?? []).map((value) => value.trim())))
        .filter((value) => value.length > 0 && value.length <= maxLength)
        .sort()
        .slice(0, 20);
      for (const value of normalizedValues) params.append(field, value);
    }
    if (developmentPhases.has(location.trialLinkedDrugGlobalPhase ?? "")) {
      params.set("linked_drug_global_phase", location.trialLinkedDrugGlobalPhase ?? "");
    }
    if (location.trialLinkedDrugOrganizationCountryRegion?.trim()) {
      params.set(
        "linked_drug_organization_country_region",
        location.trialLinkedDrugOrganizationCountryRegion.trim().slice(0, 120),
      );
    }
    const trialRoleEntityIds = Array.from(
      new Set((location.trialRoleEntityIds ?? []).map((entityId) => entityId.toLowerCase())),
    )
      .filter((entityId) => entityIdPattern.test(entityId))
      .sort()
      .slice(0, 20);
    if (trialRoleEntityIds.length) {
      for (const entityId of trialRoleEntityIds) params.append("role_entity_ids", entityId);
      if (trialEntityRoles.has(location.trialRoleEntityRole ?? "")) {
        params.set("role_entity_role", location.trialRoleEntityRole ?? "");
      }
    } else if (location.trialRoleEntityId && entityIdPattern.test(location.trialRoleEntityId)) {
      params.set("role_entity_id", location.trialRoleEntityId.toLowerCase());
      if (trialEntityRoles.has(location.trialRoleEntityRole ?? "")) {
        params.set("role_entity_role", location.trialRoleEntityRole ?? "");
      }
    }
    if (["true", "false"].includes(location.trialHasKeyResult ?? "")) {
      params.set("has_key_result", location.trialHasKeyResult ?? "");
    }
    if (location.trialPublicationId?.trim()) {
      params.set("publication_id", location.trialPublicationId.trim().slice(0, 240));
    }
    if (location.trialConference?.trim()) {
      params.set("conference", location.trialConference.trim().slice(0, 500));
    }
    if (boundedIsoDate(location.trialDisclosedFrom ?? "")) {
      params.set("disclosed_from", location.trialDisclosedFrom ?? "");
    }
    if (boundedIsoDate(location.trialDisclosedTo ?? "")) {
      params.set("disclosed_to", location.trialDisclosedTo ?? "");
    }
    appendLocationSort(
      params,
      location.trialSort,
      trialSortFields,
      location.trialSortBy,
      location.trialSortDirection,
      "last_update_posted",
    );
    if (location.trialDisplayMode === "landscape") params.set("display", "landscape");
    if (location.trialAnalysisView === "table") params.set("analysis_view", "table");
    if (location.trialId && entityIdPattern.test(location.trialId)) {
      params.set("trial", location.trialId.toLowerCase());
      if (
        location.trialSection &&
        location.trialSection !== "overview" &&
        trialDossierSectionSet.has(location.trialSection)
      ) {
        params.set("section", location.trialSection);
      }
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "patents") {
    if (location.applicant?.trim()) params.set("applicant", location.applicant.trim().slice(0, 300));
    if (location.patentEntityId && entityIdPattern.test(location.patentEntityId)) {
      params.set("entity_id", location.patentEntityId.toLowerCase());
    }
    if (boundedIsoDate(location.patentPriorityFrom ?? ""))
      params.set("priority_from", location.patentPriorityFrom ?? "");
    if (boundedIsoDate(location.patentPriorityTo ?? "")) params.set("priority_to", location.patentPriorityTo ?? "");
    if (boundedIsoDate(location.patentExpirationFrom ?? "")) {
      params.set("expiration_from", location.patentExpirationFrom ?? "");
    }
    if (boundedIsoDate(location.patentExpirationTo ?? ""))
      params.set("expiration_to", location.patentExpirationTo ?? "");
    if (location.patentDisplayMode === "landscape") params.set("display", "landscape");
    if (location.patentAnalysisView === "table") params.set("analysis_view", "table");
    if (location.legalStatus?.trim()) params.set("legal_status", location.legalStatus.trim().slice(0, 120));
    appendLocationSort(
      params,
      location.patentSort,
      patentSortFields,
      location.patentSortBy,
      location.patentSortDirection,
      "priority_date",
    );
    if (location.patentId && entityIdPattern.test(location.patentId)) {
      params.set("patent", location.patentId.toLowerCase());
      if (
        location.patentSection &&
        location.patentSection !== "overview" &&
        patentDossierSectionSet.has(location.patentSection)
      ) {
        params.set("section", location.patentSection);
      }
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "deals") {
    if (location.dealType?.trim()) params.set("deal_type", location.dealType.trim().slice(0, 100));
    if (dealStatuses.has(location.dealStatus ?? "")) params.set("status", location.dealStatus ?? "");
    if (dealDirections.has(location.dealDirection ?? "")) params.set("direction", location.dealDirection ?? "");
    if (location.dealDirectionReferenceJurisdiction?.trim()) {
      params.set("direction_reference_jurisdiction", location.dealDirectionReferenceJurisdiction.trim().slice(0, 120));
    }
    if (location.dealTerritory?.trim()) params.set("territory", location.dealTerritory.trim().slice(0, 240));
    if (location.dealAssetEntityId && entityIdPattern.test(location.dealAssetEntityId)) {
      params.set("asset_entity_id", location.dealAssetEntityId.toLowerCase());
    }
    if (location.dealTargetEntityId && entityIdPattern.test(location.dealTargetEntityId)) {
      params.set("target_entity_id", location.dealTargetEntityId.toLowerCase());
    }
    if (location.dealDiseaseEntityId && entityIdPattern.test(location.dealDiseaseEntityId)) {
      params.set("disease_entity_id", location.dealDiseaseEntityId.toLowerCase());
    }
    for (const value of location.dealAssetModalities ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 120) params.append("asset_modality", normalized);
    }
    for (const value of location.dealAssetProgramTags ?? []) {
      const normalized = value.trim();
      if (normalized && normalized.length <= 240) params.append("asset_program_tag", normalized);
    }
    if (location.dealParty?.trim()) params.set("party", location.dealParty.trim().slice(0, 500));
    if (location.dealPartyEntityId && entityIdPattern.test(location.dealPartyEntityId)) {
      params.set("party_entity_id", location.dealPartyEntityId.toLowerCase());
    }
    if (dealPartyRoles.has(location.dealPartyRole ?? "")) params.set("party_role", location.dealPartyRole ?? "");
    if (location.dealPartyCountryRegion?.trim()) {
      params.set("party_country_region", location.dealPartyCountryRegion.trim().slice(0, 120));
    }
    if (location.dealPartyOrganizationType?.trim()) {
      params.set("party_organization_type", location.dealPartyOrganizationType.trim().slice(0, 120));
    }
    if (developmentPhases.has(location.dealDevelopmentPhaseAtTransaction ?? "")) {
      params.set("development_phase_at_transaction", location.dealDevelopmentPhaseAtTransaction ?? "");
    }
    if (developmentPhases.has(location.dealCurrentDevelopmentPhase ?? "")) {
      params.set("current_development_phase", location.dealCurrentDevelopmentPhase ?? "");
    }
    if (dealRightTypes.has(location.dealRightType ?? "")) params.set("right_type", location.dealRightType ?? "");
    if (location.dealRightsTerritory?.trim()) {
      params.set("rights_territory", location.dealRightsTerritory.trim().slice(0, 240));
    }
    if (/^[A-Z]{3}$/.test(location.dealCurrency ?? "")) params.set("currency", location.dealCurrency ?? "");
    for (const [key, value] of [
      ["announced_from", location.dealAnnouncedFrom],
      ["announced_to", location.dealAnnouncedTo],
      ["terminated_from", location.dealTerminatedFrom],
      ["terminated_to", location.dealTerminatedTo],
      ["source_updated_from", location.dealSourceUpdatedFrom],
      ["source_updated_to", location.dealSourceUpdatedTo],
    ] as const) {
      if (boundedIsoDate(value ?? "")) params.set(key, value ?? "");
    }
    for (const [key, value] of [
      ["upfront_amount_min", location.dealUpfrontAmountMin],
      ["upfront_amount_max", location.dealUpfrontAmountMax],
      ["total_potential_amount_min", location.dealTotalPotentialAmountMin],
      ["total_potential_amount_max", location.dealTotalPotentialAmountMax],
    ] as const) {
      if (boundedAmount(value ?? "")) params.set(key, value ?? "");
    }
    const hasDealCurrency = /^[A-Z]{3}$/.test(location.dealCurrency ?? "");
    const dealSort = location.dealSort?.some(
      (criterion) => dealAmountSortFields.has(criterion.field) && !hasDealCurrency,
    )
      ? undefined
      : location.dealSort;
    const dealLegacySortBy =
      location.dealSortBy && dealAmountSortFields.has(location.dealSortBy) && !hasDealCurrency
        ? "announced_at"
        : location.dealSortBy;
    appendLocationSort(params, dealSort, dealSortFields, dealLegacySortBy, location.dealSortDirection, "announced_at");
    if (location.dealDisplayMode === "landscape") params.set("display", "landscape");
    if (
      location.dealAnalysisDimension &&
      location.dealAnalysisDimension !== "all" &&
      dealAnalysisDimensions.has(location.dealAnalysisDimension)
    ) {
      params.set("analysis_dimension", location.dealAnalysisDimension);
    }
    if (location.dealAnalysisView === "table") params.set("analysis_view", "table");
    if (location.dealAnalysisLimit && location.dealAnalysisLimit !== 8) {
      params.set("analysis_top", String(location.dealAnalysisLimit));
    }
    if (location.dealId && entityIdPattern.test(location.dealId)) {
      params.set("deal", location.dealId.toLowerCase());
      if (
        location.dealSection &&
        location.dealSection !== "overview" &&
        dealDossierSectionSet.has(location.dealSection)
      ) {
        params.set("section", location.dealSection);
      }
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "regulatory") {
    if (location.regulatoryDisplayMode === "landscape") params.set("display", "landscape");
    if (location.regulatoryAnalysisView === "table") params.set("analysis_view", "table");
    if (location.regulatoryAgency?.trim()) params.set("agency", location.regulatoryAgency.trim().slice(0, 80));
    if (location.regulatoryJurisdiction?.trim()) {
      params.set("jurisdiction", location.regulatoryJurisdiction.trim().slice(0, 120));
    }
    if (location.regulatoryEventType?.trim()) {
      params.set("event_type", location.regulatoryEventType.trim().slice(0, 40));
    }
    if (location.regulatoryStatus?.trim()) params.set("status", location.regulatoryStatus.trim().slice(0, 120));
    if (regulatoryDesignationTypes.has(location.regulatoryDesignationType ?? "")) {
      params.set("designation_type", location.regulatoryDesignationType ?? "");
    }
    if (regulatoryLabelChangeTypes.has(location.regulatoryLabelChangeType ?? "")) {
      params.set("label_change_type", location.regulatoryLabelChangeType ?? "");
    }
    if (["true", "false"].includes(location.regulatoryBoxedWarning ?? "")) {
      params.set("boxed_warning", location.regulatoryBoxedWarning ?? "");
    }
    if (regulatorySafetySignalTypes.has(location.regulatorySafetySignalType ?? "")) {
      params.set("safety_signal_type", location.regulatorySafetySignalType ?? "");
    }
    if (regulatorySafetySeverities.has(location.regulatorySafetySeverity ?? "")) {
      params.set("safety_severity", location.regulatorySafetySeverity ?? "");
    }
    if (regulatorySafetyStatuses.has(location.regulatorySafetyStatus ?? "")) {
      params.set("safety_status", location.regulatorySafetyStatus ?? "");
    }
    for (const [key, value] of [
      ["decision_from", location.regulatoryDecisionFrom],
      ["decision_to", location.regulatoryDecisionTo],
      ["source_updated_from", location.regulatorySourceUpdatedFrom],
      ["source_updated_to", location.regulatorySourceUpdatedTo],
    ] as const) {
      if (boundedIsoDate(value ?? "")) params.set(key, value ?? "");
    }
    appendLocationSort(
      params,
      location.regulatorySort,
      regulatorySortFields,
      location.regulatorySortBy,
      location.regulatorySortDirection,
      "decision_date",
    );
    if (location.regulatoryEventId && entityIdPattern.test(location.regulatoryEventId)) {
      params.set("regulatory_event", location.regulatoryEventId.toLowerCase());
    }
    const compareIds = boundedEntityIdList(location.regulatoryCompareIds?.join(",") ?? "");
    if (compareIds.length) params.set("compare", compareIds.join(","));
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "epidemiology") {
    if (location.epidemiologyDisplayMode === "landscape") params.set("display", "landscape");
    if (location.epidemiologyAnalysisView === "table") params.set("analysis_view", "table");
    if (location.epidemiologyDiseaseEntityId && entityIdPattern.test(location.epidemiologyDiseaseEntityId)) {
      params.set("disease_entity_id", location.epidemiologyDiseaseEntityId.toLowerCase());
    }
    if (location.epidemiologyMeasure?.trim()) params.set("measure", location.epidemiologyMeasure.trim().slice(0, 40));
    if (location.epidemiologyGeography?.trim()) {
      params.set("geography", location.epidemiologyGeography.trim().slice(0, 160));
    }
    if (location.epidemiologyUnit?.trim()) params.set("unit", location.epidemiologyUnit.trim().slice(0, 120));
    if (location.epidemiologyPatientPopulationId && entityIdPattern.test(location.epidemiologyPatientPopulationId)) {
      params.set("patient_population_id", location.epidemiologyPatientPopulationId.toLowerCase());
    }
    if (location.epidemiologyPopulationScope?.trim()) {
      params.set("population_scope", location.epidemiologyPopulationScope.trim().slice(0, 500));
    }
    if (location.epidemiologyAgeGroup?.trim()) {
      params.set("age_group", location.epidemiologyAgeGroup.trim().slice(0, 120));
    }
    if (location.epidemiologySex?.trim()) params.set("sex", location.epidemiologySex.trim().slice(0, 80));
    if (boundedIsoDate(location.epidemiologyPeriodStartFrom ?? "")) {
      params.set("period_start_from", location.epidemiologyPeriodStartFrom ?? "");
    }
    if (boundedIsoDate(location.epidemiologyPeriodEndTo ?? "")) {
      params.set("period_end_to", location.epidemiologyPeriodEndTo ?? "");
    }
    appendLocationSort(
      params,
      location.epidemiologySort,
      epidemiologySortFields,
      location.epidemiologySortBy,
      location.epidemiologySortDirection,
      "period_end",
    );
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "news") {
    if (location.newsEventType?.trim()) params.set("event_type", location.newsEventType.trim().slice(0, 40));
    if (location.newsPublisher?.trim()) params.set("publisher", location.newsPublisher.trim().slice(0, 300));
    if (location.newsLanguage?.trim()) params.set("language", location.newsLanguage.trim().slice(0, 40));
    if (location.newsVenue?.trim()) params.set("venue", location.newsVenue.trim().slice(0, 240));
    if (boundedIsoDate(location.newsPublishedFrom ?? ""))
      params.set("published_from", location.newsPublishedFrom ?? "");
    if (boundedIsoDate(location.newsPublishedTo ?? "")) params.set("published_to", location.newsPublishedTo ?? "");
    if (location.newsContentScope === "research") params.set("content_scope", "research");
    if (location.newsEntityId && entityIdPattern.test(location.newsEntityId)) {
      params.set("entity_id", location.newsEntityId.toLowerCase());
    }
    if (location.newsDisplayMode === "timeline") params.set("display", "timeline");
    if (location.newsDisplayMode === "landscape") params.set("display", "landscape");
    if (location.newsAnalysisView === "table") params.set("analysis_view", "table");
    appendLocationSort(
      params,
      location.newsSort,
      newsSortFields,
      location.newsSortBy,
      location.newsSortDirection,
      "published_at",
    );
    if (location.newsEventId && entityIdPattern.test(location.newsEventId)) {
      params.set("news_event", location.newsEventId.toLowerCase());
    }
    if (location.offset && location.offset > 0) params.set("offset", String(Math.min(100_000, location.offset)));
  }
  if (location.view === "collections" && location.collectionId && entityIdPattern.test(location.collectionId)) {
    params.set("collection", location.collectionId.toLowerCase());
    const compareIds = boundedEntityIdList(location.collectionCompareEntityIds?.join(",") ?? "");
    if (compareIds.length) params.set("compare", compareIds.join(","));
  }
  const query = params.toString();
  const path = workbenchPaths[location.workbench];
  return query ? `${path}?${query}` : path;
}
