import { dealSortFields } from "../../lib/contracts/deals";
import { epidemiologySortFields } from "../../lib/contracts/epidemiology";
import { entitySortFields } from "../../lib/contracts/intelligence";
import type { SavedSearch } from "../../lib/contracts/monitoring";
import { newsSortFields } from "../../lib/contracts/news";
import { patentSortFields } from "../../lib/contracts/patents";
import { pipelineSortFields } from "../../lib/contracts/pipeline";
import { regulatorySortFields } from "../../lib/contracts/regulatory";
import { parseSortTokens, type SortCriterion, type SortDirection } from "../../lib/contracts/sorting";
import { trialSortFields } from "../../lib/contracts/trials";
import type {
  ClinicalTrialSavedSearchQuery,
  DealSavedSearchQuery,
  EntitySearchQuery,
  EpidemiologySavedSearchQuery,
  NewsSavedSearchQuery,
  PatentSavedSearchQuery,
  PipelineSavedSearchQuery,
  RegulatorySavedSearchQuery,
} from "../../lib/generated";
import type { WorkspaceLocation } from "../../lib/workspaceRouting";

function savedRepeatedValues(value: unknown): string[] {
  const values = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
  return Array.from(
    new Set(values.filter((item): item is string => typeof item === "string" && item.trim().length > 0)),
  )
    .map((item) => item.trim())
    .slice(0, 20);
}

function savedSort<Field extends string>(
  tokens: readonly string[] | null | undefined,
  fields: readonly Field[],
  sortBy: Field,
  sortDirection: SortDirection,
): SortCriterion<Field>[] {
  return parseSortTokens(tokens ?? [], new Set(fields), { field: sortBy, direction: sortDirection });
}

export function savedSearchLocation(saved: SavedSearch): WorkspaceLocation {
  if (saved.query_type === "chemistry_search") {
    return {
      workbench: "research",
      view: "chemistry",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      chemistrySavedSearchId: saved.id,
      invalidChemistrySavedSearchId: false,
    };
  }
  if (saved.query_type === "pipeline_search") {
    const query = saved.query_json as PipelineSavedSearchQuery;
    const sort = savedSort(
      query.sort,
      pipelineSortFields,
      query.sort_by ?? "status_date",
      query.sort_direction ?? "desc",
    );
    return {
      workbench: "research",
      view: "pipeline",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      pipelineModalities: Array.isArray(query.modality) ? query.modality : query.modality ? [query.modality] : [],
      pipelineInnovationTypes: query.innovation_type ?? [],
      pipelineTherapeuticAreas: query.therapeutic_area ?? [],
      pipelineDrugCategories: query.drug_category ?? [],
      pipelineProgramStatus: query.program_status ?? "",
      pipelineOrganizationRole: query.organization_role ?? "",
      pipelineOrganizationType: query.organization_type ?? "",
      pipelineOrganizationCountryRegion: query.organization_country_region ?? "",
      phase: query.phase ?? "",
      geography: query.geography ?? "",
      pipelineStatusDateFrom: query.status_date_from ?? "",
      pipelineStatusDateTo: query.status_date_to ?? "",
      pipelineDrugEntityId: query.drug_entity_id ?? "",
      pipelineTargetEntityId: query.target_entity_id ?? "",
      pipelineTargetCombinationKey: query.target_combination_key ?? "",
      pipelineDiseaseEntityId: query.disease_entity_id ?? "",
      pipelineOrganizationEntityId: query.organization_entity_id ?? "",
      pipelineGlobalPhase: query.global_phase ?? "",
      pipelineChinaPhase: query.china_phase ?? "",
      pipelineGlobalPhaseStartedFrom: query.global_phase_started_from ?? "",
      pipelineGlobalPhaseStartedTo: query.global_phase_started_to ?? "",
      pipelineChinaPhaseStartedFrom: query.china_phase_started_from ?? "",
      pipelineChinaPhaseStartedTo: query.china_phase_started_to ?? "",
      pipelineDevelopmentRightsRegion: query.development_rights_region ?? "",
      pipelineCommercializationRightsRegion: query.commercialization_rights_region ?? "",
      pipelineProgramTags: Array.isArray(query.program_tag)
        ? query.program_tag
        : query.program_tag
          ? [query.program_tag]
          : [],
      pipelineMilestoneType: query.milestone_type ?? "",
      pipelineMilestoneFrom: query.milestone_from ?? "",
      pipelineMilestoneTo: query.milestone_to ?? "",
      pipelineHasClinicalResults:
        query.has_clinical_results === undefined ? "" : query.has_clinical_results ? "true" : "false",
      pipelineClinicalResultEvaluation: query.clinical_result_evaluation ?? "",
      pipelineHasDeal: query.has_deal === undefined ? "" : query.has_deal ? "true" : "false",
      pipelineDealCurrency: query.deal_currency ?? "",
      pipelineDealTotalPotentialAmountMin: query.deal_total_potential_amount_min?.toString() ?? "",
      pipelineDealTotalPotentialAmountMax: query.deal_total_potential_amount_max?.toString() ?? "",
      pipelineSort: sort,
      pipelineSortBy: sort[0]?.field ?? "status_date",
      pipelineSortDirection: sort[0]?.direction ?? "desc",
      pipelineDisplayMode: query.display_mode ?? "list",
      pipelineAnalysisDimension: query.analysis_dimension ?? "all",
      pipelineAnalysisView: query.analysis_view ?? "chart",
      pipelineAnalysisLimit: query.analysis_limit ?? 8,
      pipelineAnalysisStageScope: query.analysis_stage_scope ?? "overall",
      pipelineTargetAggregation: query.target_aggregation ?? "all",
      offset: 0,
    };
  }
  if (saved.query_type === "clinical_trial_search") {
    const query = saved.query_json as ClinicalTrialSavedSearchQuery;
    const sort = savedSort(
      query.sort,
      trialSortFields,
      query.sort_by ?? "last_update_posted",
      query.sort_direction ?? "desc",
    );
    return {
      workbench: "research",
      view: "trials",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      registry: query.registry ?? "",
      trialStatus: query.status ?? "",
      trialPhase: query.phase ?? "",
      studyType: query.study_type ?? "",
      trialAcronym: query.acronym ?? "",
      trialInitiationType: query.initiation_type ?? "",
      trialTherapyLine: query.therapy_line ?? "",
      trialHasResults: query.has_results === true ? "true" : query.has_results === false ? "false" : "",
      trialResultEvaluation: query.result_evaluation ?? "",
      trialResultsPostedFrom: query.results_posted_from ?? "",
      trialResultsPostedTo: query.results_posted_to ?? "",
      trialInvestigationalDrug: query.investigational_drug ?? "",
      trialCombinationDrug: query.combination_drug ?? "",
      trialInvestigationalTarget: query.investigational_target ?? "",
      trialCombinationTarget: query.combination_target ?? "",
      trialInvestigationalDrugEntityIds: query.investigational_drug_entity_ids ?? [],
      trialCombinationDrugEntityIds: query.combination_drug_entity_ids ?? [],
      trialInvestigationalTargetEntityIds: query.investigational_target_entity_ids ?? [],
      trialCombinationTargetEntityIds: query.combination_target_entity_ids ?? [],
      trialLinkedDrugModalities: query.linked_drug_modality ?? [],
      trialLinkedDrugInnovationTypes: query.linked_drug_innovation_type ?? [],
      trialLinkedDrugCategories: query.linked_drug_category ?? [],
      trialLinkedDrugProgramTags: query.linked_drug_program_tag ?? [],
      trialLinkedDrugGlobalPhase: query.linked_drug_global_phase ?? "",
      trialLinkedDrugOrganizationCountryRegion: query.linked_drug_organization_country_region ?? "",
      trialRoleEntityId: query.role_entity_id ?? "",
      trialRoleEntityIds: query.role_entity_ids ?? [],
      trialRoleEntityRole: query.role_entity_role ?? "",
      trialHasKeyResult: query.has_key_result === true ? "true" : query.has_key_result === false ? "false" : "",
      trialPublicationId: query.publication_id ?? "",
      trialConference: query.conference ?? "",
      trialDisclosedFrom: query.disclosed_from ?? "",
      trialDisclosedTo: query.disclosed_to ?? "",
      trialSort: sort,
      trialSortBy: sort[0]?.field ?? "last_update_posted",
      trialSortDirection: sort[0]?.direction ?? "desc",
      trialDisplayMode: query.display_mode ?? "list",
      trialAnalysisView: query.analysis_view ?? "chart",
      trialId: null,
      invalidTrialId: false,
      trialSection: "overview",
      offset: 0,
    };
  }
  if (saved.query_type === "patent_search") {
    const query = saved.query_json as PatentSavedSearchQuery;
    const sort = savedSort(
      query.sort,
      patentSortFields,
      query.sort_by ?? "priority_date",
      query.sort_direction ?? "desc",
    );
    return {
      workbench: "research",
      view: "patents",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      applicant: query.applicant ?? "",
      legalStatus: query.legal_status ?? "",
      patentSort: sort,
      patentSortBy: sort[0]?.field ?? "priority_date",
      patentSortDirection: sort[0]?.direction ?? "desc",
      patentId: null,
      invalidPatentId: false,
      patentSection: "overview",
      patentDisplayMode: query.display_mode ?? "list",
      patentAnalysisView: query.analysis_view ?? "chart",
      patentEntityId: query.entity_id ?? "",
      patentPriorityFrom: query.priority_from ?? "",
      patentPriorityTo: query.priority_to ?? "",
      patentExpirationFrom: query.expiration_from ?? "",
      patentExpirationTo: query.expiration_to ?? "",
      offset: 0,
    };
  }
  if (saved.query_type === "deal_search") {
    const query = saved.query_json as DealSavedSearchQuery;
    const requestedSort = savedSort(
      query.sort,
      dealSortFields,
      query.sort_by ?? "announced_at",
      query.sort_direction ?? "desc",
    );
    const sort =
      requestedSort.some((criterion) => ["upfront_amount", "total_potential_amount"].includes(criterion.field)) &&
      !query.currency
        ? [{ field: "announced_at" as const, direction: "desc" as const }]
        : requestedSort;
    return {
      workbench: "research",
      view: "deals",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      dealType: query.deal_type ?? "",
      dealStatus: query.status ?? "",
      dealDirection: query.direction ?? "",
      dealDirectionReferenceJurisdiction: query.direction_reference_jurisdiction ?? "",
      dealTerritory: query.territory ?? "",
      dealAssetEntityId: query.asset_entity_id ?? "",
      dealTargetEntityId: query.target_entity_id ?? "",
      dealDiseaseEntityId: query.disease_entity_id ?? "",
      dealAssetModalities: savedRepeatedValues(query.asset_modality),
      dealAssetProgramTags: savedRepeatedValues(query.asset_program_tag),
      dealParty: query.party ?? "",
      dealPartyEntityId: query.party_entity_id ?? "",
      dealPartyRole: query.party_role ?? "",
      dealPartyCountryRegion: query.party_country_region ?? "",
      dealPartyOrganizationType: query.party_organization_type ?? "",
      dealDevelopmentPhaseAtTransaction: query.development_phase_at_transaction ?? "",
      dealCurrentDevelopmentPhase: query.current_development_phase ?? "",
      dealRightType: query.right_type ?? "",
      dealRightsTerritory: query.rights_territory ?? "",
      dealCurrency: query.currency ?? "",
      dealAnnouncedFrom: query.announced_from ?? "",
      dealAnnouncedTo: query.announced_to ?? "",
      dealTerminatedFrom: query.terminated_from ?? "",
      dealTerminatedTo: query.terminated_to ?? "",
      dealSourceUpdatedFrom: query.source_updated_from ?? "",
      dealSourceUpdatedTo: query.source_updated_to ?? "",
      dealUpfrontAmountMin: query.upfront_amount_min?.toString() ?? "",
      dealUpfrontAmountMax: query.upfront_amount_max?.toString() ?? "",
      dealTotalPotentialAmountMin: query.total_potential_amount_min?.toString() ?? "",
      dealTotalPotentialAmountMax: query.total_potential_amount_max?.toString() ?? "",
      dealSort: sort,
      dealSortBy: sort[0]?.field ?? "announced_at",
      dealSortDirection: sort[0]?.direction ?? "desc",
      dealDisplayMode: query.display_mode ?? "list",
      dealAnalysisDimension: query.analysis_dimension ?? "all",
      dealAnalysisView: query.analysis_view ?? "chart",
      dealAnalysisLimit: query.analysis_limit ?? 8,
      dealId: null,
      invalidDealId: false,
      dealSection: "overview",
      offset: 0,
    };
  }
  if (saved.query_type === "regulatory_search") {
    const query = saved.query_json as RegulatorySavedSearchQuery;
    const sort = savedSort(
      query.sort,
      regulatorySortFields,
      query.sort_by ?? "decision_date",
      query.sort_direction ?? "desc",
    );
    return {
      workbench: "research",
      view: "regulatory",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      regulatoryAgency: query.agency ?? "",
      regulatoryJurisdiction: query.jurisdiction ?? "",
      regulatoryEventType: query.event_type ?? "",
      regulatoryDisplayMode: query.display_mode ?? "list",
      regulatoryAnalysisView: query.analysis_view ?? "chart",
      regulatoryStatus: query.status ?? "",
      regulatoryDesignationType: query.designation_type ?? "",
      regulatoryLabelChangeType: query.label_change_type ?? "",
      regulatoryBoxedWarning:
        query.has_boxed_warning === true ? "true" : query.has_boxed_warning === false ? "false" : "",
      regulatorySafetySignalType: query.safety_signal_type ?? "",
      regulatorySafetySeverity: query.safety_severity ?? "",
      regulatorySafetyStatus: query.safety_status ?? "",
      regulatoryDecisionFrom: query.decision_from ?? "",
      regulatoryDecisionTo: query.decision_to ?? "",
      regulatorySourceUpdatedFrom: query.source_updated_from ?? "",
      regulatorySourceUpdatedTo: query.source_updated_to ?? "",
      regulatorySort: sort,
      regulatorySortBy: sort[0]?.field ?? "decision_date",
      regulatorySortDirection: sort[0]?.direction ?? "desc",
      regulatoryEventId: null,
      invalidRegulatoryEventId: false,
      regulatoryCompareIds: [],
      offset: 0,
    };
  }
  if (saved.query_type === "epidemiology_search") {
    const query = saved.query_json as EpidemiologySavedSearchQuery;
    const sort = savedSort(
      query.sort,
      epidemiologySortFields,
      query.sort_by ?? "period_end",
      query.sort_direction ?? "desc",
    );
    return {
      workbench: "research",
      view: "epidemiology",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      epidemiologyDiseaseEntityId: query.disease_entity_id ?? "",
      epidemiologyMeasure: query.measure ?? "",
      epidemiologyGeography: query.geography ?? "",
      epidemiologyUnit: query.unit ?? "",
      epidemiologyPatientPopulationId: query.patient_population_id ?? "",
      epidemiologyPopulationScope: query.population_scope ?? "",
      epidemiologyAgeGroup: query.age_group ?? "",
      epidemiologySex: query.sex ?? "",
      epidemiologyPeriodStartFrom: query.period_start_from ?? "",
      epidemiologyPeriodEndTo: query.period_end_to ?? "",
      epidemiologySort: sort,
      epidemiologySortBy: sort[0]?.field ?? "period_end",
      epidemiologySortDirection: sort[0]?.direction ?? "desc",
      epidemiologyDisplayMode: query.display_mode ?? "list",
      epidemiologyAnalysisView: query.analysis_view ?? "chart",
      offset: 0,
    };
  }
  if (saved.query_type === "news_search") {
    const query = saved.query_json as NewsSavedSearchQuery;
    const sort = savedSort(query.sort, newsSortFields, query.sort_by ?? "published_at", query.sort_direction ?? "desc");
    return {
      workbench: "research",
      view: "news",
      query: query.q ?? "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      newsEventType: query.event_type ?? "",
      newsPublisher: query.publisher ?? "",
      newsLanguage: query.language ?? "",
      newsVenue: query.venue ?? "",
      newsPublishedFrom: query.published_from ?? "",
      newsPublishedTo: query.published_to ?? "",
      newsContentScope: query.content_scope === "research" ? "research" : "",
      newsEntityId: query.entity_id ?? "",
      newsDisplayMode: query.display_mode ?? "list",
      newsSort: sort,
      newsSortBy: sort[0]?.field ?? "published_at",
      newsSortDirection: sort[0]?.direction ?? "desc",
      newsEventId: null,
      invalidNewsEventId: false,
      newsAnalysisView: query.analysis_view ?? "chart",
      offset: 0,
    };
  }
  const query = saved.query_json as EntitySearchQuery;
  const entityTypes = query.entity_types?.length ? query.entity_types : query.entity_type ? [query.entity_type] : [];
  const sort = savedSort(query.sort, entitySortFields, query.sort_by ?? "relevance", query.sort_direction ?? "desc");
  return {
    workbench: "research",
    view: "explorer",
    query: query.q ?? "",
    entityType: entityTypes.length === 1 ? (entityTypes[0] ?? "") : "",
    entityTypes,
    entityIncludeRelated: query.include_related ?? false,
    reviewStatus: query.review_status ?? "",
    entitySort: sort,
    entitySortBy: sort[0]?.field ?? "relevance",
    entitySortDirection: sort[0]?.direction ?? "desc",
    explorerDisplayMode: query.display_mode ?? "list",
    explorerAnalysisView: query.analysis_view ?? "chart",
    entityId: null,
    invalidEntityId: false,
  };
}
