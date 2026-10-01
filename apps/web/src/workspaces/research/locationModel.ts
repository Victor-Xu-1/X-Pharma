import { emptyPipelineSearchFilters, type PipelineSearchFilters } from "../../lib/contracts/pipeline";
import {
  type CompanyDossierSection,
  type DiseaseDossierSection,
  type DrugDossierSection,
  type EntityDossierSection,
  parseWorkbenchLocation,
  type TargetDossierSection,
  type WorkspaceLocation,
} from "../../lib/workspaceRouting";

export const specializedSectionByEntitySection: Record<
  EntityDossierSection,
  {
    company: CompanyDossierSection;
    disease: DiseaseDossierSection;
    drug: DrugDossierSection;
    target: TargetDossierSection;
  }
> = {
  overview: { company: "overview", disease: "overview", drug: "overview", target: "overview" },
  company_intelligence: { company: "overview", disease: "overview", drug: "overview", target: "overview" },
  relationships: { company: "relationships", disease: "relationships", drug: "relationships", target: "relationships" },
  programs: { company: "pipeline", disease: "pipeline", drug: "pipeline", target: "pipeline" },
  activities: { company: "overview", disease: "overview", drug: "activities", target: "activities" },
  clinical_trials: { company: "trials", disease: "trials", drug: "trials", target: "trials" },
  patents: { company: "patents", disease: "patents", drug: "patents", target: "patents" },
  deals: { company: "deals", disease: "deals", drug: "deals", target: "deals" },
  regulatory_events: { company: "regulatory", disease: "regulatory", drug: "regulatory", target: "regulatory" },
  news_events: { company: "news", disease: "news", drug: "news", target: "news" },
  structures: { company: "overview", disease: "overview", drug: "structures", target: "structures" },
};

export function trialRoleGroupIds(
  location: WorkspaceLocation,
  role: string,
  groupedIds: string[] | undefined,
): string[] {
  if (groupedIds?.length) return groupedIds;
  if (location.trialRoleEntityRole !== role) return [];
  return Array.from(
    new Set([...(location.trialRoleEntityIds ?? []), location.trialRoleEntityId ?? ""].filter(Boolean)),
  ).sort();
}

export function pipelineFiltersFromLocation(location: WorkspaceLocation, fallbackTargetId = ""): PipelineSearchFilters {
  return {
    ...emptyPipelineSearchFilters(),
    query: location.query,
    modalities: location.pipelineModalities ?? [],
    innovationTypes: location.pipelineInnovationTypes ?? [],
    therapeuticAreas: location.pipelineTherapeuticAreas ?? [],
    drugCategories: location.pipelineDrugCategories ?? [],
    programStatus: location.pipelineProgramStatus === "all" ? "" : (location.pipelineProgramStatus ?? ""),
    organizationRole: location.pipelineOrganizationRole ?? "",
    organizationType: location.pipelineOrganizationType ?? "",
    organizationCountryRegion: location.pipelineOrganizationCountryRegion ?? "",
    phase: location.phase ?? "",
    geography: location.geography ?? "",
    statusDateFrom: location.pipelineStatusDateFrom ?? "",
    statusDateTo: location.pipelineStatusDateTo ?? "",
    drugEntityId: location.pipelineDrugEntityId ?? "",
    targetEntityId: location.pipelineTargetEntityId || fallbackTargetId,
    targetCombinationKey: location.pipelineTargetCombinationKey ?? "",
    diseaseEntityId: location.pipelineDiseaseEntityId ?? "",
    organizationEntityId: location.pipelineOrganizationEntityId ?? "",
    globalPhase: location.pipelineGlobalPhase ?? "",
    chinaPhase: location.pipelineChinaPhase ?? "",
    globalPhaseStartedFrom: location.pipelineGlobalPhaseStartedFrom ?? "",
    globalPhaseStartedTo: location.pipelineGlobalPhaseStartedTo ?? "",
    chinaPhaseStartedFrom: location.pipelineChinaPhaseStartedFrom ?? "",
    chinaPhaseStartedTo: location.pipelineChinaPhaseStartedTo ?? "",
    developmentRightsRegion: location.pipelineDevelopmentRightsRegion ?? "",
    commercializationRightsRegion: location.pipelineCommercializationRightsRegion ?? "",
    programTags: location.pipelineProgramTags ?? [],
    milestoneType: location.pipelineMilestoneType ?? "",
    milestoneFrom: location.pipelineMilestoneFrom ?? "",
    milestoneTo: location.pipelineMilestoneTo ?? "",
    hasClinicalResults: location.pipelineHasClinicalResults ?? "",
    clinicalResultEvaluation: location.pipelineClinicalResultEvaluation ?? "",
    hasDeal: location.pipelineHasDeal ?? "",
    dealCurrency: location.pipelineDealCurrency ?? "",
    dealTotalPotentialAmountMin: location.pipelineDealTotalPotentialAmountMin ?? "",
    dealTotalPotentialAmountMax: location.pipelineDealTotalPotentialAmountMax ?? "",
    sortBy: (location.pipelineSortBy ?? "status_date") as PipelineSearchFilters["sortBy"],
    sortDirection: (location.pipelineSortDirection ?? "desc") as PipelineSearchFilters["sortDirection"],
    sort: location.pipelineSort as PipelineSearchFilters["sort"],
    offset: location.offset ?? 0,
  };
}

export function drugReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  if (parsed.view === "pipeline") return parsed;
  if (parsed.view === "target" && parsed.targetSection === "pipeline" && parsed.entityId) return parsed;
  if (parsed.view === "collections" && parsed.collectionId && !parsed.invalidCollectionId) return parsed;
  if (parsed.view === "trials" && parsed.trialId && !parsed.invalidTrialId) return parsed;
  return null;
}

export function targetReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  if (parsed.view === "drug" && parsed.entityId && !parsed.invalidEntityId) return parsed;
  if (parsed.view === "trials" && parsed.trialId && !parsed.invalidTrialId) return parsed;
  return null;
}

export function trialReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  return ["target", "drug", "company", "disease", "entity"].includes(parsed.view) &&
    parsed.entityId &&
    !parsed.invalidEntityId
    ? parsed
    : null;
}

export function trialReturnLabel(location: WorkspaceLocation | null): string | undefined {
  if (!location) return undefined;
  if (location.view === "target") return "返回靶点档案";
  if (location.view === "drug") return "返回药物档案";
  if (location.view === "company") return "返回公司档案";
  if (location.view === "disease") return "返回疾病档案";
  return "返回实体档案";
}

export function locationWithPipelineFilters(
  location: WorkspaceLocation,
  filters: PipelineSearchFilters,
): WorkspaceLocation {
  return {
    ...location,
    query: filters.query,
    pipelineModalities: filters.modalities,
    pipelineInnovationTypes: filters.innovationTypes,
    pipelineTherapeuticAreas: filters.therapeuticAreas,
    pipelineDrugCategories: filters.drugCategories,
    pipelineProgramStatus: location.view === "target" && filters.programStatus === "" ? "all" : filters.programStatus,
    pipelineOrganizationRole: filters.organizationRole,
    pipelineOrganizationType: filters.organizationType,
    pipelineOrganizationCountryRegion: filters.organizationCountryRegion,
    phase: filters.phase,
    geography: filters.geography,
    pipelineStatusDateFrom: filters.statusDateFrom,
    pipelineStatusDateTo: filters.statusDateTo,
    pipelineDrugEntityId: filters.drugEntityId,
    pipelineTargetEntityId:
      location.view === "target" && filters.targetEntityId === location.entityId ? "" : filters.targetEntityId,
    pipelineTargetCombinationKey: filters.targetCombinationKey,
    pipelineDiseaseEntityId: filters.diseaseEntityId,
    pipelineOrganizationEntityId: filters.organizationEntityId,
    pipelineGlobalPhase: filters.globalPhase,
    pipelineChinaPhase: filters.chinaPhase,
    pipelineGlobalPhaseStartedFrom: filters.globalPhaseStartedFrom,
    pipelineGlobalPhaseStartedTo: filters.globalPhaseStartedTo,
    pipelineChinaPhaseStartedFrom: filters.chinaPhaseStartedFrom,
    pipelineChinaPhaseStartedTo: filters.chinaPhaseStartedTo,
    pipelineDevelopmentRightsRegion: filters.developmentRightsRegion,
    pipelineCommercializationRightsRegion: filters.commercializationRightsRegion,
    pipelineProgramTags: filters.programTags,
    pipelineMilestoneType: filters.milestoneType,
    pipelineMilestoneFrom: filters.milestoneFrom,
    pipelineMilestoneTo: filters.milestoneTo,
    pipelineHasClinicalResults: filters.hasClinicalResults,
    pipelineClinicalResultEvaluation: filters.clinicalResultEvaluation,
    pipelineHasDeal: filters.hasDeal,
    pipelineDealCurrency: filters.dealCurrency,
    pipelineDealTotalPotentialAmountMin: filters.dealTotalPotentialAmountMin,
    pipelineDealTotalPotentialAmountMax: filters.dealTotalPotentialAmountMax,
    pipelineSort: filters.sort,
    pipelineSortBy: filters.sortBy,
    pipelineSortDirection: filters.sortDirection,
    offset: filters.offset,
  };
}
