import {
  companyDossierSectionSet,
  dealAmountSortFields,
  dealAnalysisDimensions,
  dealAnalysisLimits,
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
  pipelineAnalysisLimits,
  pipelineAnalysisStageScopes,
  pipelineOrganizationRoles,
  pipelineResultGrains,
  pipelineSortFields,
  pipelineTargetAggregations,
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
  views,
  viewWorkbenches,
  workbenchDefaults,
} from "./catalog";
import {
  boundedAmount,
  boundedEntityIdList,
  boundedEvidenceDocumentId,
  boundedIsoDate,
  boundedRepeatedEntityIds,
  boundedRepeatedValues,
  boundedTargetCombinationKey,
  locationSort,
} from "./queryValues";
import type {
  CompanyDossierSection,
  DealDossierSection,
  DiseaseDossierSection,
  DrugDossierSection,
  EntityDossierSection,
  KnowledgePanel,
  MonitoringTab,
  PatentDossierSection,
  ReturnPathNormalizer,
  TargetDossierSection,
  TrialDossierSection,
  ViewKey,
  WorkbenchKey,
  WorkspaceLocation,
} from "./types";
export function parseWorkspaceQuery(
  workbench: WorkbenchKey,
  search: string,
  normalizeReturnPath: ReturnPathNormalizer,
): WorkspaceLocation {
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
          entityIncludeRelated: params.get("related") === null || params.get("related") === "1",
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
  const returnTo = workbench === "research" ? normalizeReturnPath(params.get("from")) : undefined;
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
