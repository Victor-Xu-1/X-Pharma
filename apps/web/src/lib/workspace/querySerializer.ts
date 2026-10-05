import {
  companyDossierSectionSet,
  dealAmountSortFields,
  dealAnalysisDimensions,
  dealDirections,
  dealDossierSectionSet,
  dealPartyRoles,
  dealRightTypes,
  dealSortFields,
  dealStatuses,
  developmentPhases,
  diseaseDossierSectionSet,
  drugDossierSectionSet,
  entityDossierSectionSet,
  entityIdPattern,
  entitySortFields,
  entityTypes,
  entityTypeValues,
  epidemiologySortFields,
  monitoringTabSet,
  newsSortFields,
  patentDossierSectionSet,
  patentSortFields,
  pipelineAnalysisDimensions,
  pipelineOrganizationRoles,
  pipelineSortFields,
  regulatoryDesignationTypes,
  regulatoryLabelChangeTypes,
  regulatorySafetySeverities,
  regulatorySafetySignalTypes,
  regulatorySafetyStatuses,
  regulatorySortFields,
  reviewStatuses,
  targetDossierSectionSet,
  trialDossierSectionSet,
  trialEntityRoles,
  trialInitiationTypes,
  trialResultEvaluations,
  trialSortFields,
  trialTherapyLines,
  workbenchDefaults,
  workbenchPaths,
} from "./catalog";
import {
  appendLocationSort,
  boundedAmount,
  boundedEntityIdList,
  boundedEvidenceDocumentId,
  boundedIsoDate,
  boundedTargetCombinationKey,
} from "./queryValues";
import type { ReturnPathNormalizer, WorkspaceLocation } from "./types";
export function serializeWorkspaceLocation(
  location: Pick<
    WorkspaceLocation,
    | "workbench"
    | "view"
    | "query"
    | "entityType"
    | "entityTypes"
    | "entityIncludeRelated"
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
  normalizeReturnPath: ReturnPathNormalizer,
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
    if (location.entityIncludeRelated === false) params.set("related", "0");
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
    const returnTo = normalizeReturnPath(location.returnTo);
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
