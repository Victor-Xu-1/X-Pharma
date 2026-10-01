import { emptyPipelineSearchFilters, type PipelineSearchFilters } from "../../lib/contracts/pipeline";
import type {
  CompanyDossierSection,
  DiseaseDossierSection,
  DrugDossierSection,
  EntityDossierSection,
  TargetDossierSection,
  ViewKey,
  WorkspaceLocation,
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

const researchReturnLabels: Partial<Record<ViewKey, string>> = {
  overview: "返回用户中心",
  explorer: "返回情报检索",
  chemistry: "返回结构检索",
  pipeline: "返回管线查询",
  trials: "返回临床试验",
  patents: "返回专利检索",
  deals: "返回交易检索",
  regulatory: "返回监管检索",
  epidemiology: "返回流行病学检索",
  news: "返回新闻检索",
  target: "返回靶点档案",
  drug: "返回药物档案",
  company: "返回公司档案",
  disease: "返回疾病档案",
  entity: "返回实体档案",
  evidence: "返回原始证据",
  knowledge: "返回知识专题",
  monitoring: "返回监控与提醒",
  collections: "返回对比列表",
};

export function researchReturnLabel(location: WorkspaceLocation | null): string | undefined {
  if (!location) return undefined;
  return researchReturnLabels[location.view];
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
