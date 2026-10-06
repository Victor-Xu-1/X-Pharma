import { developmentPhases as canonicalDevelopmentPhases } from "../phasePresentation";
import type { UserRole } from "../types";
import {
  companyDossierSections,
  dealDossierSections,
  diseaseDossierSections,
  drugDossierSections,
  entityDossierSections,
  patentDossierSections,
  targetDossierSections,
  trialDossierSections,
  type ViewKey,
  type WorkbenchKey,
} from "./types";
export const targetDossierSectionSet = new Set<string>(targetDossierSections);
export const drugDossierSectionSet = new Set<string>(drugDossierSections);
export const companyDossierSectionSet = new Set<string>(companyDossierSections);
export const diseaseDossierSectionSet = new Set<string>(diseaseDossierSections);
export const trialDossierSectionSet = new Set<string>(trialDossierSections);
export const patentDossierSectionSet = new Set<string>(patentDossierSections);
export const dealDossierSectionSet = new Set<string>(dealDossierSections);
export const entityDossierSectionSet = new Set<string>(entityDossierSections);
export const monitoringTabSet = new Set<string>(["alerts", "topics", "searches"]);
export const workbenchPaths: Record<WorkbenchKey, string> = {
  research: "/workspace/research",
  internal: "/workspace/internal",
};

export function workbenchPath(workbench: WorkbenchKey): string {
  return workbenchPaths[workbench];
}

export const workbenchDefaults: Record<WorkbenchKey, ViewKey> = {
  research: "explorer",
  internal: "factory",
};

export const viewWorkbenches: Record<ViewKey, WorkbenchKey> = {
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
  environment: "internal",
};

export const views = new Set<ViewKey>([
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
  "environment",
]);

export const restrictedViews: Partial<Record<ViewKey, ReadonlySet<UserRole>>> = {
  factory: new Set(["admin", "analyst"]),
  governance: new Set(["admin", "analyst"]),
  commercial: new Set(["admin"]),
  enterprise: new Set(["admin"]),
  environment: new Set(["admin"]),
};
export const entityIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export const entityTypeValues = [
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
export const entityTypes = new Set<string>(entityTypeValues);
export const reviewStatuses = new Set(["draft", "verified", "rejected", "superseded"]);
export const entitySortFields = new Set(["relevance", "name", "entity_type", "updated_at"]);
export const developmentPhases: ReadonlySet<string> = canonicalDevelopmentPhases;
export const pipelineOrganizationRoles = new Set([
  "originator",
  "collaborator",
  "licensee",
  "licensor",
  "manufacturer",
  "other",
]);
export const pipelineSortFields = new Set([
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
export const pipelineAnalysisDimensions = new Set([
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
export const pipelineAnalysisLimits = new Set([5, 8, 20, 50, 100, 200]);
export const pipelineAnalysisStageScopes = new Set(["overall", "global", "china"]);
export const pipelineTargetAggregations = new Set(["all", "primary"]);
export const pipelineResultGrains = new Set(["program", "drug"]);
export const trialSortFields = new Set([
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
export const patentSortFields = new Set(["priority_date", "family_identifier", "legal_status", "expiration_date"]);
export const dealSortFields = new Set([
  "announced_at",
  "name",
  "deal_type",
  "status",
  "direction",
  "territory",
  "upfront_amount",
  "total_potential_amount",
]);
export const dealAmountSortFields = new Set(["upfront_amount", "total_potential_amount"]);
export const dealAnalysisDimensions = new Set([
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
export const dealAnalysisLimits = new Set([5, 8, 20, 50]);
export const regulatorySortFields = new Set([
  "decision_date",
  "title",
  "agency",
  "jurisdiction",
  "event_type",
  "status",
  "subject",
  "source_updated_at",
]);
export const epidemiologySortFields = new Set([
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
export const newsSortFields = new Set(["published_at", "title", "event_type", "publisher", "venue"]);
export const trialResultEvaluations = new Set([
  "unfavorable",
  "not_superior",
  "non_inferior",
  "similar",
  "positive",
  "superior",
  "terminated",
]);
export const trialEntityRoles = new Set([
  "investigational_drug",
  "combination_drug",
  "investigational_target",
  "combination_target",
]);
export const trialInitiationTypes = new Set(["iit", "ist"]);
export const trialTherapyLines = new Set([
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
export const dealStatuses = new Set([
  "announced",
  "active",
  "completed",
  "terminated",
  "withdrawn",
  "superseded",
  "unknown",
]);
export const dealDirections = new Set(["domestic", "inbound", "outbound", "cross_border", "global", "undisclosed"]);
export const dealPartyRoles = new Set([
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
export const dealRightTypes = new Set([
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
export const regulatoryDesignationTypes = new Set([
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
export const regulatoryLabelChangeTypes = new Set([
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
export const regulatorySafetySignalTypes = new Set([
  "adverse_event",
  "boxed_warning",
  "contraindication",
  "risk_management",
  "recall",
  "clinical_hold",
  "postmarketing_requirement",
  "other",
]);
export const regulatorySafetySeverities = new Set([
  "informational",
  "moderate",
  "serious",
  "severe",
  "life_threatening",
  "fatal",
  "unknown",
]);
export const regulatorySafetyStatuses = new Set([
  "detected",
  "under_evaluation",
  "confirmed",
  "monitoring",
  "resolved",
  "withdrawn",
  "unknown",
]);
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
