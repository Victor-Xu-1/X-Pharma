import { emptyDealSearchFilters, validateDealSearchFilters } from "./contracts/deals";
import { emptyRegulatorySearchFilters, validateRegulatorySearchFilters } from "./contracts/regulatory";
import { validatePipelineSignalFilters } from "./pipelineSignals";
import { validateTrialResultFilters } from "./trialFilters";
import type { WorkspaceLocation } from "./workspaceRouting";

export type ProfessionalSearchDomain =
  | "pipeline"
  | "trials"
  | "patents"
  | "deals"
  | "regulatory"
  | "epidemiology"
  | "news";

export type ProfessionalDatePreset = "all" | "last_month" | "last_6_months" | "last_year" | "custom";
export type PatentEntityType = "drug" | "target" | "disease" | "organization";

type ResolvableProfessionalDatePreset = Exclude<ProfessionalDatePreset, "custom">;

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function currentLocalDate(): string {
  const now = new Date();
  const year = String(now.getFullYear()).padStart(4, "0");
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function subtractCalendarMonths(value: string, months: number): string {
  if (!ISO_DATE_PATTERN.test(value)) throw new RangeError("today must use YYYY-MM-DD");
  const [year, month, day] = value.split("-").map(Number);
  const source = new Date(Date.UTC(year, month - 1, day));
  if (source.getUTCFullYear() !== year || source.getUTCMonth() !== month - 1 || source.getUTCDate() !== day) {
    throw new RangeError("today must be a valid calendar date");
  }
  const targetMonthIndex = year * 12 + (month - 1) - months;
  const targetYear = Math.floor(targetMonthIndex / 12);
  const targetMonth = targetMonthIndex - targetYear * 12;
  const lastTargetDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  return `${String(targetYear).padStart(4, "0")}-${String(targetMonth + 1).padStart(2, "0")}-${String(
    Math.min(day, lastTargetDay),
  ).padStart(2, "0")}`;
}

export function resolveProfessionalDatePreset(
  preset: ResolvableProfessionalDatePreset,
  today = currentLocalDate(),
): { from: string; to: string } {
  if (preset === "all") return { from: "", to: "" };
  const months = preset === "last_month" ? 1 : preset === "last_6_months" ? 6 : 12;
  return { from: subtractCalendarMonths(today, months), to: today };
}

export function identifyProfessionalDatePreset(
  from: string,
  to: string,
  today = currentLocalDate(),
): ProfessionalDatePreset {
  for (const preset of ["all", "last_month", "last_6_months", "last_year"] as const) {
    const range = resolveProfessionalDatePreset(preset, today);
    if (range.from === from && range.to === to) return preset;
  }
  return "custom";
}

export interface ProfessionalSearchDraft {
  domain: ProfessionalSearchDomain;
  query: string;
  drugEntityId: string;
  targetEntityId: string;
  diseaseEntityId: string;
  organizationEntityId: string;
  modalities: string[];
  pipelineInnovationTypes: string[];
  pipelineTherapeuticAreas: string[];
  pipelineDrugCategories: string[];
  pipelineProgramStatus: string;
  pipelineOrganizationRole: string;
  pipelineOrganizationType: string;
  pipelineOrganizationCountryRegion: string;
  phase: string;
  geography: string;
  statusDateFrom: string;
  statusDateTo: string;
  pipelineGlobalPhase: string;
  pipelineChinaPhase: string;
  pipelineGlobalPhaseStartedFrom: string;
  pipelineGlobalPhaseStartedTo: string;
  pipelineChinaPhaseStartedFrom: string;
  pipelineChinaPhaseStartedTo: string;
  pipelineDevelopmentRightsRegion: string;
  pipelineCommercializationRightsRegion: string;
  pipelineProgramTags: string[];
  pipelineMilestoneType: string;
  pipelineMilestoneFrom: string;
  pipelineMilestoneTo: string;
  pipelineHasClinicalResults: "" | "true" | "false";
  pipelineClinicalResultEvaluation: string;
  pipelineHasDeal: "" | "true" | "false";
  pipelineDealCurrency: string;
  pipelineDealTotalPotentialAmountMin: string;
  pipelineDealTotalPotentialAmountMax: string;
  registry: string;
  trialStatus: string;
  trialPhase: string;
  studyType: string;
  trialHasResults: string;
  trialAcronym: string;
  trialInitiationType: string;
  trialTherapyLine: string;
  trialResultEvaluation: string;
  trialResultsPostedFrom: string;
  trialResultsPostedTo: string;
  trialHasKeyResult: string;
  trialPublicationId: string;
  trialConference: string;
  trialDisclosedFrom: string;
  trialDisclosedTo: string;
  patentEntityType: PatentEntityType;
  patentEntityId: string;
  applicant: string;
  legalStatus: string;
  patentPriorityFrom: string;
  patentPriorityTo: string;
  patentExpirationFrom: string;
  patentExpirationTo: string;
  dealType: string;
  dealStatus: string;
  dealDirection: string;
  dealDirectionReferenceJurisdiction: string;
  dealAssetEntityId: string;
  dealTargetEntityId: string;
  dealDiseaseEntityId: string;
  dealAssetModalities: string[];
  dealAssetProgramTags: string[];
  dealPartyEntityId: string;
  dealTerritory: string;
  dealPartyRole: string;
  dealPartyCountryRegion: string;
  dealPartyOrganizationType: string;
  dealDevelopmentPhaseAtTransaction: string;
  dealCurrentDevelopmentPhase: string;
  dealRightType: string;
  dealRightsTerritory: string;
  dealCurrency: string;
  dealAnnouncedFrom: string;
  dealAnnouncedTo: string;
  dealTerminatedFrom: string;
  dealTerminatedTo: string;
  dealSourceUpdatedFrom: string;
  dealSourceUpdatedTo: string;
  dealUpfrontAmountMin: string;
  dealUpfrontAmountMax: string;
  dealTotalPotentialAmountMin: string;
  dealTotalPotentialAmountMax: string;
  regulatoryAgency: string;
  regulatoryJurisdiction: string;
  regulatoryEventType: string;
  regulatoryStatus: string;
  regulatoryDesignationType: string;
  regulatoryLabelChangeType: string;
  regulatoryBoxedWarning: "" | "true" | "false";
  regulatorySafetySignalType: string;
  regulatorySafetySeverity: string;
  regulatorySafetyStatus: string;
  regulatoryDecisionFrom: string;
  regulatoryDecisionTo: string;
  regulatorySourceUpdatedFrom: string;
  regulatorySourceUpdatedTo: string;
  epidemiologyMeasure: string;
  epidemiologyGeography: string;
  epidemiologyUnit: string;
  epidemiologyPatientPopulationId: string;
  epidemiologyPopulationScope: string;
  epidemiologyAgeGroup: string;
  epidemiologySex: string;
  epidemiologyPeriodStartFrom: string;
  epidemiologyPeriodEndTo: string;
  newsEntityId: string;
  newsEventType: string;
  newsPublisher: string;
  newsLanguage: string;
  newsVenue: string;
  newsPublishedFrom: string;
  newsPublishedTo: string;
  newsContentScope: "" | "research";
}

export function createProfessionalSearchDraft(
  domain: ProfessionalSearchDomain = "pipeline",
  query = "",
): ProfessionalSearchDraft {
  return {
    domain,
    query,
    drugEntityId: "",
    targetEntityId: "",
    diseaseEntityId: "",
    organizationEntityId: "",
    modalities: [],
    pipelineInnovationTypes: [],
    pipelineTherapeuticAreas: [],
    pipelineDrugCategories: [],
    pipelineProgramStatus: "",
    pipelineOrganizationRole: "",
    pipelineOrganizationType: "",
    pipelineOrganizationCountryRegion: "",
    phase: "",
    geography: "",
    statusDateFrom: "",
    statusDateTo: "",
    pipelineGlobalPhase: "",
    pipelineChinaPhase: "",
    pipelineGlobalPhaseStartedFrom: "",
    pipelineGlobalPhaseStartedTo: "",
    pipelineChinaPhaseStartedFrom: "",
    pipelineChinaPhaseStartedTo: "",
    pipelineDevelopmentRightsRegion: "",
    pipelineCommercializationRightsRegion: "",
    pipelineProgramTags: [],
    pipelineMilestoneType: "",
    pipelineMilestoneFrom: "",
    pipelineMilestoneTo: "",
    pipelineHasClinicalResults: "",
    pipelineClinicalResultEvaluation: "",
    pipelineHasDeal: "",
    pipelineDealCurrency: "",
    pipelineDealTotalPotentialAmountMin: "",
    pipelineDealTotalPotentialAmountMax: "",
    registry: "",
    trialStatus: "",
    trialPhase: "",
    studyType: "",
    trialHasResults: "",
    trialAcronym: "",
    trialInitiationType: "",
    trialTherapyLine: "",
    trialResultEvaluation: "",
    trialResultsPostedFrom: "",
    trialResultsPostedTo: "",
    trialHasKeyResult: "",
    trialPublicationId: "",
    trialConference: "",
    trialDisclosedFrom: "",
    trialDisclosedTo: "",
    patentEntityType: "target",
    patentEntityId: "",
    applicant: "",
    legalStatus: "",
    patentPriorityFrom: "",
    patentPriorityTo: "",
    patentExpirationFrom: "",
    patentExpirationTo: "",
    dealType: "",
    dealStatus: "",
    dealDirection: "",
    dealDirectionReferenceJurisdiction: "",
    dealAssetEntityId: "",
    dealTargetEntityId: "",
    dealDiseaseEntityId: "",
    dealAssetModalities: [],
    dealAssetProgramTags: [],
    dealPartyEntityId: "",
    dealTerritory: "",
    dealPartyRole: "",
    dealPartyCountryRegion: "",
    dealPartyOrganizationType: "",
    dealDevelopmentPhaseAtTransaction: "",
    dealCurrentDevelopmentPhase: "",
    dealRightType: "",
    dealRightsTerritory: "",
    dealCurrency: "",
    dealAnnouncedFrom: "",
    dealAnnouncedTo: "",
    dealTerminatedFrom: "",
    dealTerminatedTo: "",
    dealSourceUpdatedFrom: "",
    dealSourceUpdatedTo: "",
    dealUpfrontAmountMin: "",
    dealUpfrontAmountMax: "",
    dealTotalPotentialAmountMin: "",
    dealTotalPotentialAmountMax: "",
    regulatoryAgency: "",
    regulatoryJurisdiction: "",
    regulatoryEventType: "",
    regulatoryStatus: "",
    regulatoryDesignationType: "",
    regulatoryLabelChangeType: "",
    regulatoryBoxedWarning: "",
    regulatorySafetySignalType: "",
    regulatorySafetySeverity: "",
    regulatorySafetyStatus: "",
    regulatoryDecisionFrom: "",
    regulatoryDecisionTo: "",
    regulatorySourceUpdatedFrom: "",
    regulatorySourceUpdatedTo: "",
    epidemiologyMeasure: "",
    epidemiologyGeography: "",
    epidemiologyUnit: "",
    epidemiologyPatientPopulationId: "",
    epidemiologyPopulationScope: "",
    epidemiologyAgeGroup: "",
    epidemiologySex: "",
    epidemiologyPeriodStartFrom: "",
    epidemiologyPeriodEndTo: "",
    newsEntityId: "",
    newsEventType: "",
    newsPublisher: "",
    newsLanguage: "",
    newsVenue: "",
    newsPublishedFrom: "",
    newsPublishedTo: "",
    newsContentScope: "",
  };
}

const dateRanges: Record<
  ProfessionalSearchDomain,
  Array<{ from: keyof ProfessionalSearchDraft; to: keyof ProfessionalSearchDraft; label: string }>
> = {
  pipeline: [
    { from: "statusDateFrom", to: "statusDateTo", label: "状态日期" },
    {
      from: "pipelineGlobalPhaseStartedFrom",
      to: "pipelineGlobalPhaseStartedTo",
      label: "全球阶段开始日期",
    },
    {
      from: "pipelineChinaPhaseStartedFrom",
      to: "pipelineChinaPhaseStartedTo",
      label: "中国阶段开始日期",
    },
    { from: "pipelineMilestoneFrom", to: "pipelineMilestoneTo", label: "里程碑日期" },
  ],
  trials: [
    { from: "trialResultsPostedFrom", to: "trialResultsPostedTo", label: "结果发布日期" },
    { from: "trialDisclosedFrom", to: "trialDisclosedTo", label: "结果披露日期" },
  ],
  patents: [
    { from: "patentPriorityFrom", to: "patentPriorityTo", label: "优先权日期" },
    { from: "patentExpirationFrom", to: "patentExpirationTo", label: "到期日期" },
  ],
  deals: [],
  regulatory: [],
  epidemiology: [{ from: "epidemiologyPeriodStartFrom", to: "epidemiologyPeriodEndTo", label: "统计周期" }],
  news: [{ from: "newsPublishedFrom", to: "newsPublishedTo", label: "发布日期" }],
};

export function validateProfessionalSearch(draft: ProfessionalSearchDraft): string | null {
  for (const range of dateRanges[draft.domain]) {
    const from = draft[range.from];
    const to = draft[range.to];
    if (typeof from === "string" && typeof to === "string" && from && to && from > to) {
      return `${range.label}起始值不能晚于结束值`;
    }
  }
  if (draft.domain === "pipeline") {
    return validatePipelineSignalFilters({
      hasClinicalResults: draft.pipelineHasClinicalResults,
      clinicalResultEvaluation: draft.pipelineClinicalResultEvaluation,
      hasDeal: draft.pipelineHasDeal,
      dealCurrency: draft.pipelineDealCurrency,
      dealTotalPotentialAmountMin: draft.pipelineDealTotalPotentialAmountMin,
      dealTotalPotentialAmountMax: draft.pipelineDealTotalPotentialAmountMax,
    });
  }
  if (draft.domain === "trials") {
    return validateTrialResultFilters({
      hasResults: draft.trialHasResults,
      resultEvaluation: draft.trialResultEvaluation,
    });
  }
  if (draft.domain === "deals") {
    return validateDealSearchFilters({
      ...emptyDealSearchFilters,
      query: draft.query,
      dealType: draft.dealType,
      status: draft.dealStatus,
      direction: draft.dealDirection,
      directionReferenceJurisdiction: draft.dealDirectionReferenceJurisdiction,
      territory: draft.dealTerritory,
      assetEntityId: draft.dealAssetEntityId,
      targetEntityId: draft.dealTargetEntityId,
      diseaseEntityId: draft.dealDiseaseEntityId,
      assetModalities: draft.dealAssetModalities,
      assetProgramTags: draft.dealAssetProgramTags,
      partyEntityId: draft.dealPartyEntityId,
      partyRole: draft.dealPartyRole,
      partyCountryRegion: draft.dealPartyCountryRegion,
      partyOrganizationType: draft.dealPartyOrganizationType,
      developmentPhaseAtTransaction: draft.dealDevelopmentPhaseAtTransaction,
      currentDevelopmentPhase: draft.dealCurrentDevelopmentPhase,
      rightType: draft.dealRightType,
      rightsTerritory: draft.dealRightsTerritory,
      currency: draft.dealCurrency,
      announcedFrom: draft.dealAnnouncedFrom,
      announcedTo: draft.dealAnnouncedTo,
      terminatedFrom: draft.dealTerminatedFrom,
      terminatedTo: draft.dealTerminatedTo,
      sourceUpdatedFrom: draft.dealSourceUpdatedFrom,
      sourceUpdatedTo: draft.dealSourceUpdatedTo,
      upfrontAmountMin: draft.dealUpfrontAmountMin,
      upfrontAmountMax: draft.dealUpfrontAmountMax,
      totalPotentialAmountMin: draft.dealTotalPotentialAmountMin,
      totalPotentialAmountMax: draft.dealTotalPotentialAmountMax,
    });
  }
  if (draft.domain === "regulatory") {
    return validateRegulatorySearchFilters({
      ...emptyRegulatorySearchFilters,
      query: draft.query,
      agency: draft.regulatoryAgency,
      jurisdiction: draft.regulatoryJurisdiction,
      eventType: draft.regulatoryEventType,
      status: draft.regulatoryStatus,
      designationType: draft.regulatoryDesignationType,
      labelChangeType: draft.regulatoryLabelChangeType,
      boxedWarning: draft.regulatoryBoxedWarning,
      safetySignalType: draft.regulatorySafetySignalType,
      safetySeverity: draft.regulatorySafetySeverity,
      safetyStatus: draft.regulatorySafetyStatus,
      decisionFrom: draft.regulatoryDecisionFrom,
      decisionTo: draft.regulatoryDecisionTo,
      sourceUpdatedFrom: draft.regulatorySourceUpdatedFrom,
      sourceUpdatedTo: draft.regulatorySourceUpdatedTo,
    });
  }
  return null;
}

export function countProfessionalConditions(draft: ProfessionalSearchDraft): number {
  const location = professionalSearchLocation(draft);
  return Object.entries(location).filter(
    ([key, value]) =>
      ![
        "workbench",
        "view",
        "entityType",
        "reviewStatus",
        "entityId",
        "invalidEntityId",
        "offset",
        "pipelineDisplayMode",
        "newsDisplayMode",
      ].includes(key) && (Array.isArray(value) ? value.length > 0 : Boolean(value)),
  ).length;
}

function baseLocation(draft: ProfessionalSearchDraft): WorkspaceLocation {
  return {
    workbench: "research",
    view: draft.domain,
    query: draft.query.trim(),
    entityType: "",
    reviewStatus: "",
    entityId: null,
    invalidEntityId: false,
    offset: 0,
  };
}

export function professionalSearchLocation(draft: ProfessionalSearchDraft): WorkspaceLocation {
  const base = baseLocation(draft);
  switch (draft.domain) {
    case "pipeline":
      return {
        ...base,
        pipelineModalities: draft.modalities,
        pipelineInnovationTypes: draft.pipelineInnovationTypes,
        pipelineTherapeuticAreas: draft.pipelineTherapeuticAreas,
        pipelineDrugCategories: draft.pipelineDrugCategories,
        pipelineProgramStatus: draft.pipelineProgramStatus,
        pipelineOrganizationRole: draft.pipelineOrganizationRole,
        pipelineOrganizationType: draft.pipelineOrganizationType.trim(),
        pipelineOrganizationCountryRegion: draft.pipelineOrganizationCountryRegion.trim(),
        phase: draft.phase,
        geography: draft.geography.trim(),
        pipelineStatusDateFrom: draft.statusDateFrom,
        pipelineStatusDateTo: draft.statusDateTo,
        pipelineDrugEntityId: draft.drugEntityId,
        pipelineTargetEntityId: draft.targetEntityId,
        pipelineDiseaseEntityId: draft.diseaseEntityId,
        pipelineOrganizationEntityId: draft.organizationEntityId,
        pipelineGlobalPhase: draft.pipelineGlobalPhase,
        pipelineChinaPhase: draft.pipelineChinaPhase,
        pipelineGlobalPhaseStartedFrom: draft.pipelineGlobalPhaseStartedFrom,
        pipelineGlobalPhaseStartedTo: draft.pipelineGlobalPhaseStartedTo,
        pipelineChinaPhaseStartedFrom: draft.pipelineChinaPhaseStartedFrom,
        pipelineChinaPhaseStartedTo: draft.pipelineChinaPhaseStartedTo,
        pipelineDevelopmentRightsRegion: draft.pipelineDevelopmentRightsRegion.trim(),
        pipelineCommercializationRightsRegion: draft.pipelineCommercializationRightsRegion.trim(),
        pipelineProgramTags: draft.pipelineProgramTags,
        pipelineMilestoneType: draft.pipelineMilestoneType,
        pipelineMilestoneFrom: draft.pipelineMilestoneFrom,
        pipelineMilestoneTo: draft.pipelineMilestoneTo,
        pipelineHasClinicalResults: draft.pipelineHasClinicalResults,
        pipelineClinicalResultEvaluation: draft.pipelineClinicalResultEvaluation,
        pipelineHasDeal: draft.pipelineHasDeal,
        pipelineDealCurrency: draft.pipelineDealCurrency.trim().toUpperCase(),
        pipelineDealTotalPotentialAmountMin: draft.pipelineDealTotalPotentialAmountMin,
        pipelineDealTotalPotentialAmountMax: draft.pipelineDealTotalPotentialAmountMax,
        pipelineDisplayMode: "list",
      };
    case "trials":
      return {
        ...base,
        registry: draft.registry,
        trialStatus: draft.trialStatus,
        trialPhase: draft.trialPhase,
        studyType: draft.studyType,
        trialHasResults: draft.trialHasResults,
        trialAcronym: draft.trialAcronym.trim(),
        trialInitiationType: draft.trialInitiationType,
        trialTherapyLine: draft.trialTherapyLine,
        trialResultEvaluation: draft.trialResultEvaluation,
        trialResultsPostedFrom: draft.trialResultsPostedFrom,
        trialResultsPostedTo: draft.trialResultsPostedTo,
        trialHasKeyResult: draft.trialHasKeyResult,
        trialPublicationId: draft.trialPublicationId.trim(),
        trialConference: draft.trialConference.trim(),
        trialDisclosedFrom: draft.trialDisclosedFrom,
        trialDisclosedTo: draft.trialDisclosedTo,
        trialId: null,
        invalidTrialId: false,
      };
    case "patents":
      return {
        ...base,
        patentEntityId: draft.patentEntityId,
        applicant: draft.applicant.trim(),
        legalStatus: draft.legalStatus,
        patentPriorityFrom: draft.patentPriorityFrom,
        patentPriorityTo: draft.patentPriorityTo,
        patentExpirationFrom: draft.patentExpirationFrom,
        patentExpirationTo: draft.patentExpirationTo,
      };
    case "deals":
      return {
        ...base,
        dealType: draft.dealType,
        dealStatus: draft.dealStatus,
        dealDirection: draft.dealDirection,
        dealDirectionReferenceJurisdiction: draft.dealDirectionReferenceJurisdiction.trim(),
        dealAssetEntityId: draft.dealAssetEntityId,
        dealTargetEntityId: draft.dealTargetEntityId,
        dealDiseaseEntityId: draft.dealDiseaseEntityId,
        dealAssetModalities: draft.dealAssetModalities,
        dealAssetProgramTags: draft.dealAssetProgramTags,
        dealPartyEntityId: draft.dealPartyEntityId,
        dealTerritory: draft.dealTerritory.trim(),
        dealPartyRole: draft.dealPartyRole,
        dealPartyCountryRegion: draft.dealPartyCountryRegion.trim(),
        dealPartyOrganizationType: draft.dealPartyOrganizationType.trim(),
        dealDevelopmentPhaseAtTransaction: draft.dealDevelopmentPhaseAtTransaction,
        dealCurrentDevelopmentPhase: draft.dealCurrentDevelopmentPhase,
        dealRightType: draft.dealRightType,
        dealRightsTerritory: draft.dealRightsTerritory.trim(),
        dealCurrency: draft.dealCurrency.trim().toUpperCase(),
        dealAnnouncedFrom: draft.dealAnnouncedFrom,
        dealAnnouncedTo: draft.dealAnnouncedTo,
        dealTerminatedFrom: draft.dealTerminatedFrom,
        dealTerminatedTo: draft.dealTerminatedTo,
        dealSourceUpdatedFrom: draft.dealSourceUpdatedFrom,
        dealSourceUpdatedTo: draft.dealSourceUpdatedTo,
        dealUpfrontAmountMin: draft.dealUpfrontAmountMin,
        dealUpfrontAmountMax: draft.dealUpfrontAmountMax,
        dealTotalPotentialAmountMin: draft.dealTotalPotentialAmountMin,
        dealTotalPotentialAmountMax: draft.dealTotalPotentialAmountMax,
        dealId: null,
        invalidDealId: false,
      };
    case "regulatory":
      return {
        ...base,
        regulatoryAgency: draft.regulatoryAgency,
        regulatoryJurisdiction: draft.regulatoryJurisdiction.trim(),
        regulatoryEventType: draft.regulatoryEventType,
        regulatoryStatus: draft.regulatoryStatus.trim(),
        regulatoryDesignationType: draft.regulatoryDesignationType,
        regulatoryLabelChangeType: draft.regulatoryLabelChangeType,
        regulatoryBoxedWarning: draft.regulatoryBoxedWarning,
        regulatorySafetySignalType: draft.regulatorySafetySignalType,
        regulatorySafetySeverity: draft.regulatorySafetySeverity,
        regulatorySafetyStatus: draft.regulatorySafetyStatus,
        regulatoryDecisionFrom: draft.regulatoryDecisionFrom,
        regulatoryDecisionTo: draft.regulatoryDecisionTo,
        regulatorySourceUpdatedFrom: draft.regulatorySourceUpdatedFrom,
        regulatorySourceUpdatedTo: draft.regulatorySourceUpdatedTo,
        regulatoryEventId: null,
        invalidRegulatoryEventId: false,
      };
    case "epidemiology":
      return {
        ...base,
        epidemiologyDiseaseEntityId: draft.diseaseEntityId,
        epidemiologyMeasure: draft.epidemiologyMeasure,
        epidemiologyGeography: draft.epidemiologyGeography.trim(),
        epidemiologyUnit: draft.epidemiologyUnit.trim(),
        epidemiologyPatientPopulationId: draft.epidemiologyPatientPopulationId,
        epidemiologyPopulationScope: draft.epidemiologyPopulationScope.trim(),
        epidemiologyAgeGroup: draft.epidemiologyAgeGroup.trim(),
        epidemiologySex: draft.epidemiologySex,
        epidemiologyPeriodStartFrom: draft.epidemiologyPeriodStartFrom,
        epidemiologyPeriodEndTo: draft.epidemiologyPeriodEndTo,
      };
    case "news":
      return {
        ...base,
        newsEntityId: draft.newsEntityId,
        newsEventType: draft.newsEventType,
        newsPublisher: draft.newsPublisher.trim(),
        newsLanguage: draft.newsLanguage,
        newsVenue: draft.newsVenue.trim(),
        newsPublishedFrom: draft.newsPublishedFrom,
        newsPublishedTo: draft.newsPublishedTo,
        newsContentScope: draft.newsContentScope,
        newsDisplayMode: draft.newsContentScope === "research" ? "timeline" : "list",
      };
  }
}
