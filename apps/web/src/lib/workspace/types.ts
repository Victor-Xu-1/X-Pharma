import type { SortCriterion, SortDirection } from "../contracts/sorting";

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
  | "enterprise"
  | "environment";

export interface WorkspaceLocation {
  workbench: WorkbenchKey;
  view: ViewKey;
  query: string;
  entityType: string;
  entityTypes?: string[];
  entityIncludeRelated?: boolean;
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

export type ReturnPathNormalizer = (value: string | null | undefined) => string | undefined;
