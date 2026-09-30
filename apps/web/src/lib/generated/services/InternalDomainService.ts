/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AgentChemistrySearchRead } from '../models/AgentChemistrySearchRead';
import type { AgentEntitySearchResult } from '../models/AgentEntitySearchResult';
import type { AgentEvidenceSearchResult } from '../models/AgentEvidenceSearchResult';
import type { AgentPageResult_BioactivityRead_ } from '../models/AgentPageResult_BioactivityRead_';
import type { AgentPageResult_ClinicalTrialSearchItemRead_ } from '../models/AgentPageResult_ClinicalTrialSearchItemRead_';
import type { AgentPageResult_CompanyTimelineEventRead_ } from '../models/AgentPageResult_CompanyTimelineEventRead_';
import type { AgentPageResult_CompetitiveProgramRead_ } from '../models/AgentPageResult_CompetitiveProgramRead_';
import type { AgentPageResult_CompoundStructureRead_ } from '../models/AgentPageResult_CompoundStructureRead_';
import type { AgentPageResult_DealSearchItemRead_ } from '../models/AgentPageResult_DealSearchItemRead_';
import type { AgentPageResult_EpidemiologyObservationSearchItemRead_ } from '../models/AgentPageResult_EpidemiologyObservationSearchItemRead_';
import type { AgentPageResult_KnowledgePageSummary_ } from '../models/AgentPageResult_KnowledgePageSummary_';
import type { AgentPageResult_NewsEventSearchItemRead_ } from '../models/AgentPageResult_NewsEventSearchItemRead_';
import type { AgentPageResult_PatentFamilySearchItemRead_ } from '../models/AgentPageResult_PatentFamilySearchItemRead_';
import type { AgentPageResult_RegulatoryEventSearchItemRead_ } from '../models/AgentPageResult_RegulatoryEventSearchItemRead_';
import type { AgentPageResult_SarActivityRead_ } from '../models/AgentPageResult_SarActivityRead_';
import type { AgentPageResult_TargetEvidenceRead_ } from '../models/AgentPageResult_TargetEvidenceRead_';
import type { ChemistrySearchRequest } from '../models/ChemistrySearchRequest';
import type { DealDirection } from '../models/DealDirection';
import type { DealPartyRole } from '../models/DealPartyRole';
import type { DealRightType } from '../models/DealRightType';
import type { DealStatus } from '../models/DealStatus';
import type { DevelopmentPhase } from '../models/DevelopmentPhase';
import type { EntityDossierResponse } from '../models/EntityDossierResponse';
import type { EntityType } from '../models/EntityType';
import type { EvidenceSearchRequest } from '../models/EvidenceSearchRequest';
import type { KnowledgePageDetail } from '../models/KnowledgePageDetail';
import type { RecordProvenanceResponse } from '../models/RecordProvenanceResponse';
import type { RegulatoryDesignationType } from '../models/RegulatoryDesignationType';
import type { RegulatoryLabelChangeType } from '../models/RegulatoryLabelChangeType';
import type { RegulatorySafetySeverity } from '../models/RegulatorySafetySeverity';
import type { RegulatorySafetySignalType } from '../models/RegulatorySafetySignalType';
import type { RegulatorySafetyStatus } from '../models/RegulatorySafetyStatus';
import type { ReviewStatus } from '../models/ReviewStatus';
import type { TrialEntityRole } from '../models/TrialEntityRole';
import type { TrialResultEvaluation } from '../models/TrialResultEvaluation';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class InternalDomainService {
  /**
   * Search Chemistry For Agent
   * @returns AgentChemistrySearchRead Successful Response
   * @throws ApiError
   */
  public static searchChemistryForAgentInternalV1DomainChemistrySearchPost({
    xCommercialReservationId,
    requestBody,
    cursor,
  }: {
    xCommercialReservationId: string,
    requestBody: ChemistrySearchRequest,
    cursor?: (string | null),
  }): CancelablePromise<AgentChemistrySearchRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/domain/chemistry/search',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'cursor': cursor,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Clinical Trials For Agent
   * @returns AgentPageResult_ClinicalTrialSearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchClinicalTrialsForAgentInternalV1DomainClinicalTrialsGet({
    xCommercialReservationId,
    entityId,
    q,
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
    linkedDrugModality,
    linkedDrugInnovationType,
    linkedDrugCategory,
    linkedDrugProgramTag,
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
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    q?: (string | null),
    registry?: (string | null),
    status?: (string | null),
    phase?: (string | null),
    studyType?: (string | null),
    acronym?: (string | null),
    initiationType?: ('iit' | 'ist' | null),
    therapyLine?: ('first_line' | 'second_line' | 'third_or_later' | 'prevention' | 'treatment_naive' | 'add_on' | 'adjuvant' | 'neoadjuvant' | 'maintenance' | 'consolidation' | 'induction' | 'conversion' | null),
    hasResults?: (boolean | null),
    resultEvaluation?: (TrialResultEvaluation | null),
    resultsPostedFrom?: (string | null),
    resultsPostedTo?: (string | null),
    investigationalDrug?: (string | null),
    combinationDrug?: (string | null),
    investigationalTarget?: (string | null),
    combinationTarget?: (string | null),
    investigationalDrugEntityIds?: (Array<string> | null),
    combinationDrugEntityIds?: (Array<string> | null),
    investigationalTargetEntityIds?: (Array<string> | null),
    combinationTargetEntityIds?: (Array<string> | null),
    linkedDrugModality?: (Array<string> | null),
    linkedDrugInnovationType?: (Array<string> | null),
    linkedDrugCategory?: (Array<string> | null),
    linkedDrugProgramTag?: (Array<string> | null),
    linkedDrugGlobalPhase?: (DevelopmentPhase | null),
    linkedDrugOrganizationCountryRegion?: (string | null),
    roleEntityId?: (string | null),
    roleEntityIds?: (Array<string> | null),
    roleEntityRole?: (TrialEntityRole | null),
    hasKeyResult?: (boolean | null),
    publicationId?: (string | null),
    conference?: (string | null),
    disclosedFrom?: (string | null),
    disclosedTo?: (string | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('last_update_posted' | 'registry_id' | 'has_results' | 'result_evaluation' | 'overall_status' | 'enrollment' | 'study_type' | 'acronym' | 'initiation_type' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_ClinicalTrialSearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/clinical-trials',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'q': q,
        'registry': registry,
        'status': status,
        'phase': phase,
        'study_type': studyType,
        'acronym': acronym,
        'initiation_type': initiationType,
        'therapy_line': therapyLine,
        'has_results': hasResults,
        'result_evaluation': resultEvaluation,
        'results_posted_from': resultsPostedFrom,
        'results_posted_to': resultsPostedTo,
        'investigational_drug': investigationalDrug,
        'combination_drug': combinationDrug,
        'investigational_target': investigationalTarget,
        'combination_target': combinationTarget,
        'investigational_drug_entity_ids': investigationalDrugEntityIds,
        'combination_drug_entity_ids': combinationDrugEntityIds,
        'investigational_target_entity_ids': investigationalTargetEntityIds,
        'combination_target_entity_ids': combinationTargetEntityIds,
        'linked_drug_modality': linkedDrugModality,
        'linked_drug_innovation_type': linkedDrugInnovationType,
        'linked_drug_category': linkedDrugCategory,
        'linked_drug_program_tag': linkedDrugProgramTag,
        'linked_drug_global_phase': linkedDrugGlobalPhase,
        'linked_drug_organization_country_region': linkedDrugOrganizationCountryRegion,
        'role_entity_id': roleEntityId,
        'role_entity_ids': roleEntityIds,
        'role_entity_role': roleEntityRole,
        'has_key_result': hasKeyResult,
        'publication_id': publicationId,
        'conference': conference,
        'disclosed_from': disclosedFrom,
        'disclosed_to': disclosedTo,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Company Timeline For Agent
   * @returns AgentPageResult_CompanyTimelineEventRead_ Successful Response
   * @throws ApiError
   */
  public static getCompanyTimelineForAgentInternalV1DomainCompaniesCompanyIdTimelineGet({
    companyId,
    xCommercialReservationId,
    limit = 100,
    cursor,
  }: {
    companyId: string,
    xCommercialReservationId: string,
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_CompanyTimelineEventRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/companies/{company_id}/timeline',
      path: {
        'company_id': companyId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Deals For Agent
   * @returns AgentPageResult_DealSearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchDealsForAgentInternalV1DomainDealsGet({
    xCommercialReservationId,
    entityId,
    q,
    dealType,
    status,
    direction,
    directionReferenceJurisdiction,
    territory,
    assetEntityId,
    targetEntityId,
    diseaseEntityId,
    assetModality,
    assetProgramTag,
    party,
    partyEntityId,
    partyRole,
    partyCountryRegion,
    partyOrganizationType,
    developmentPhaseAtTransaction,
    currentDevelopmentPhase,
    rightType,
    rightsTerritory,
    currency,
    announcedFrom,
    announcedTo,
    terminatedFrom,
    terminatedTo,
    sourceUpdatedFrom,
    sourceUpdatedTo,
    upfrontAmountMin,
    upfrontAmountMax,
    totalPotentialAmountMin,
    totalPotentialAmountMax,
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    q?: (string | null),
    dealType?: (string | null),
    status?: (DealStatus | null),
    direction?: (DealDirection | null),
    directionReferenceJurisdiction?: (string | null),
    territory?: (string | null),
    assetEntityId?: (string | null),
    targetEntityId?: (string | null),
    diseaseEntityId?: (string | null),
    assetModality?: (Array<string> | null),
    assetProgramTag?: (Array<string> | null),
    party?: (string | null),
    partyEntityId?: (string | null),
    partyRole?: (DealPartyRole | null),
    partyCountryRegion?: (string | null),
    partyOrganizationType?: (string | null),
    developmentPhaseAtTransaction?: (DevelopmentPhase | null),
    currentDevelopmentPhase?: (DevelopmentPhase | null),
    rightType?: (DealRightType | null),
    rightsTerritory?: (string | null),
    currency?: (string | null),
    announcedFrom?: (string | null),
    announcedTo?: (string | null),
    terminatedFrom?: (string | null),
    terminatedTo?: (string | null),
    sourceUpdatedFrom?: (string | null),
    sourceUpdatedTo?: (string | null),
    upfrontAmountMin?: (number | null),
    upfrontAmountMax?: (number | null),
    totalPotentialAmountMin?: (number | null),
    totalPotentialAmountMax?: (number | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('announced_at' | 'name' | 'deal_type' | 'status' | 'direction' | 'territory' | 'upfront_amount' | 'total_potential_amount' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_DealSearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/deals',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'q': q,
        'deal_type': dealType,
        'status': status,
        'direction': direction,
        'direction_reference_jurisdiction': directionReferenceJurisdiction,
        'territory': territory,
        'asset_entity_id': assetEntityId,
        'target_entity_id': targetEntityId,
        'disease_entity_id': diseaseEntityId,
        'asset_modality': assetModality,
        'asset_program_tag': assetProgramTag,
        'party': party,
        'party_entity_id': partyEntityId,
        'party_role': partyRole,
        'party_country_region': partyCountryRegion,
        'party_organization_type': partyOrganizationType,
        'development_phase_at_transaction': developmentPhaseAtTransaction,
        'current_development_phase': currentDevelopmentPhase,
        'right_type': rightType,
        'rights_territory': rightsTerritory,
        'currency': currency,
        'announced_from': announcedFrom,
        'announced_to': announcedTo,
        'terminated_from': terminatedFrom,
        'terminated_to': terminatedTo,
        'source_updated_from': sourceUpdatedFrom,
        'source_updated_to': sourceUpdatedTo,
        'upfront_amount_min': upfrontAmountMin,
        'upfront_amount_max': upfrontAmountMax,
        'total_potential_amount_min': totalPotentialAmountMin,
        'total_potential_amount_max': totalPotentialAmountMax,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Entities For Agent
   * @returns AgentEntitySearchResult Successful Response
   * @throws ApiError
   */
  public static searchEntitiesForAgentInternalV1DomainEntitiesGet({
    billingClass,
    q,
    xCommercialReservationId,
    entityType,
    reviewStatus,
    limit = 20,
    cursor,
    sortBy,
    sortDirection,
    entityTypes,
    sort,
  }: {
    billingClass: 'entity.search' | 'entity.resolve',
    q: string,
    xCommercialReservationId: string,
    entityType?: (EntityType | null),
    reviewStatus?: (ReviewStatus | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('relevance' | 'name' | 'entity_type' | 'updated_at' | null),
    sortDirection?: ('asc' | 'desc' | null),
    entityTypes?: (Array<EntityType> | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentEntitySearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/entities',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'billing_class': billingClass,
        'q': q,
        'entity_type': entityType,
        'review_status': reviewStatus,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'entity_types': entityTypes,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Entity Dossier For Agent
   * @returns EntityDossierResponse Successful Response
   * @throws ApiError
   */
  public static getEntityDossierForAgentInternalV1DomainEntitiesEntityIdDossierGet({
    entityId,
    xCommercialReservationId,
    limit = 50,
  }: {
    entityId: string,
    xCommercialReservationId: string,
    limit?: number,
  }): CancelablePromise<EntityDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/entities/{entity_id}/dossier',
      path: {
        'entity_id': entityId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Epidemiology Observations For Agent
   * @returns AgentPageResult_EpidemiologyObservationSearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchEpidemiologyObservationsForAgentInternalV1DomainEpidemiologyObservationsGet({
    xCommercialReservationId,
    diseaseEntityId,
    q,
    measure,
    geography,
    unit,
    populationScope,
    patientPopulationId,
    ageGroup,
    sex,
    periodStartFrom,
    periodEndTo,
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    diseaseEntityId?: (string | null),
    q?: (string | null),
    measure?: (string | null),
    geography?: (string | null),
    unit?: (string | null),
    populationScope?: (string | null),
    patientPopulationId?: (string | null),
    ageGroup?: (string | null),
    sex?: (string | null),
    periodStartFrom?: (string | null),
    periodEndTo?: (string | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('period_end' | 'period_start' | 'disease' | 'measure' | 'value' | 'geography' | 'unit' | 'publisher' | 'sample_size' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_EpidemiologyObservationSearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/epidemiology-observations',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'disease_entity_id': diseaseEntityId,
        'q': q,
        'measure': measure,
        'geography': geography,
        'unit': unit,
        'population_scope': populationScope,
        'patient_population_id': patientPopulationId,
        'age_group': ageGroup,
        'sex': sex,
        'period_start_from': periodStartFrom,
        'period_end_to': periodEndTo,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Evidence For Agent
   * @returns AgentEvidenceSearchResult Successful Response
   * @throws ApiError
   */
  public static searchEvidenceForAgentInternalV1DomainEvidenceSearchPost({
    xCommercialReservationId,
    requestBody,
    cursor,
  }: {
    xCommercialReservationId: string,
    requestBody: EvidenceSearchRequest,
    cursor?: (string | null),
  }): CancelablePromise<AgentEvidenceSearchResult> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/domain/evidence/search',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'cursor': cursor,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Knowledge Pages For Agent
   * @returns AgentPageResult_KnowledgePageSummary_ Successful Response
   * @throws ApiError
   */
  public static searchKnowledgePagesForAgentInternalV1DomainKnowledgePagesGet({
    xCommercialReservationId,
    q,
    pageType,
    limit = 50,
    cursor,
  }: {
    xCommercialReservationId: string,
    q?: (string | null),
    pageType?: (string | null),
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_KnowledgePageSummary_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/knowledge/pages',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'q': q,
        'page_type': pageType,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Knowledge Page For Agent
   * @returns KnowledgePageDetail Successful Response
   * @throws ApiError
   */
  public static getKnowledgePageForAgentInternalV1DomainKnowledgePagesPageIdGet({
    pageId,
    xCommercialReservationId,
  }: {
    pageId: string,
    xCommercialReservationId: string,
  }): CancelablePromise<KnowledgePageDetail> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/knowledge/pages/{page_id}',
      path: {
        'page_id': pageId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search News Events For Agent
   * @returns AgentPageResult_NewsEventSearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchNewsEventsForAgentInternalV1DomainNewsEventsGet({
    xCommercialReservationId,
    entityId,
    q,
    eventType,
    publisher,
    language,
    venue,
    publishedFrom,
    publishedTo,
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    q?: (string | null),
    eventType?: (string | null),
    publisher?: (string | null),
    language?: (string | null),
    venue?: (string | null),
    publishedFrom?: (string | null),
    publishedTo?: (string | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('published_at' | 'title' | 'event_type' | 'publisher' | 'venue' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_NewsEventSearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/news-events',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'q': q,
        'event_type': eventType,
        'publisher': publisher,
        'language': language,
        'venue': venue,
        'published_from': publishedFrom,
        'published_to': publishedTo,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Patents For Agent
   * @returns AgentPageResult_PatentFamilySearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchPatentsForAgentInternalV1DomainPatentsGet({
    xCommercialReservationId,
    entityId,
    q,
    applicant,
    legalStatus,
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    q?: (string | null),
    applicant?: (string | null),
    legalStatus?: (string | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('priority_date' | 'family_identifier' | 'legal_status' | 'expiration_date' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_PatentFamilySearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/patents',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'q': q,
        'applicant': applicant,
        'legal_status': legalStatus,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Record Provenance For Agent
   * @returns RecordProvenanceResponse Successful Response
   * @throws ApiError
   */
  public static getRecordProvenanceForAgentInternalV1DomainProvenanceResourceTypeResourceIdGet({
    resourceType,
    resourceId,
    xCommercialReservationId,
    limit = 20,
  }: {
    resourceType: 'activity_measurement' | 'assay' | 'clinical_trial' | 'compound_structure' | 'deal' | 'development_program' | 'epidemiology_observation' | 'evidence_claim' | 'news_event' | 'patient_population' | 'patent_family' | 'regulatory_event' | 'target_profile' | 'target_evidence',
    resourceId: string,
    xCommercialReservationId: string,
    limit?: number,
  }): CancelablePromise<RecordProvenanceResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/provenance/{resource_type}/{resource_id}',
      path: {
        'resource_type': resourceType,
        'resource_id': resourceId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Regulatory Events For Agent
   * @returns AgentPageResult_RegulatoryEventSearchItemRead_ Successful Response
   * @throws ApiError
   */
  public static searchRegulatoryEventsForAgentInternalV1DomainRegulatoryEventsGet({
    xCommercialReservationId,
    entityId,
    q,
    agency,
    jurisdiction,
    eventType,
    status,
    designationType,
    labelChangeType,
    hasBoxedWarning,
    safetySignalType,
    safetySeverity,
    safetyStatus,
    decisionFrom,
    decisionTo,
    sourceUpdatedFrom,
    sourceUpdatedTo,
    limit = 100,
    cursor,
    sortBy,
    sortDirection,
    sort,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    q?: (string | null),
    agency?: (string | null),
    jurisdiction?: (string | null),
    eventType?: (string | null),
    status?: (string | null),
    designationType?: (RegulatoryDesignationType | null),
    labelChangeType?: (RegulatoryLabelChangeType | null),
    hasBoxedWarning?: (boolean | null),
    safetySignalType?: (RegulatorySafetySignalType | null),
    safetySeverity?: (RegulatorySafetySeverity | null),
    safetyStatus?: (RegulatorySafetyStatus | null),
    decisionFrom?: (string | null),
    decisionTo?: (string | null),
    sourceUpdatedFrom?: (string | null),
    sourceUpdatedTo?: (string | null),
    limit?: number,
    cursor?: (string | null),
    sortBy?: ('decision_date' | 'title' | 'agency' | 'jurisdiction' | 'event_type' | 'status' | 'subject' | 'source_updated_at' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_RegulatoryEventSearchItemRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/regulatory-events',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'q': q,
        'agency': agency,
        'jurisdiction': jurisdiction,
        'event_type': eventType,
        'status': status,
        'designation_type': designationType,
        'label_change_type': labelChangeType,
        'has_boxed_warning': hasBoxedWarning,
        'safety_signal_type': safetySignalType,
        'safety_severity': safetySeverity,
        'safety_status': safetyStatus,
        'decision_from': decisionFrom,
        'decision_to': decisionTo,
        'source_updated_from': sourceUpdatedFrom,
        'source_updated_to': sourceUpdatedTo,
        'limit': limit,
        'cursor': cursor,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Structures For Agent
   * @returns AgentPageResult_CompoundStructureRead_ Successful Response
   * @throws ApiError
   */
  public static searchStructuresForAgentInternalV1DomainStructuresGet({
    xCommercialReservationId,
    entityId,
    inchiKey,
    limit = 50,
    cursor,
  }: {
    xCommercialReservationId: string,
    entityId?: (string | null),
    inchiKey?: (string | null),
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_CompoundStructureRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/structures',
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'entity_id': entityId,
        'inchi_key': inchiKey,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Bioactivities For Agent
   * @returns AgentPageResult_BioactivityRead_ Successful Response
   * @throws ApiError
   */
  public static searchBioactivitiesForAgentInternalV1DomainTargetsTargetIdBioactivitiesGet({
    targetId,
    xCommercialReservationId,
    standardType,
    limit = 100,
    cursor,
  }: {
    targetId: string,
    xCommercialReservationId: string,
    standardType?: (string | null),
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_BioactivityRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/targets/{target_id}/bioactivities',
      path: {
        'target_id': targetId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'standard_type': standardType,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Competitive Programs For Agent
   * @returns AgentPageResult_CompetitiveProgramRead_ Successful Response
   * @throws ApiError
   */
  public static searchCompetitiveProgramsForAgentInternalV1DomainTargetsTargetIdCompetitiveProgramsGet({
    targetId,
    xCommercialReservationId,
    limit = 100,
    cursor,
    drugEntityId,
    diseaseEntityId,
    organizationEntityId,
    programStatus,
    organizationRole,
    organizationType,
    organizationCountryRegion,
    modality,
    innovationType,
    therapeuticArea,
    drugCategory,
    globalPhase,
    chinaPhase,
    globalPhaseStartedFrom,
    globalPhaseStartedTo,
    chinaPhaseStartedFrom,
    chinaPhaseStartedTo,
    developmentRightsRegion,
    commercializationRightsRegion,
    programTag,
    milestoneType,
    milestoneFrom,
    milestoneTo,
    hasClinicalResults,
    clinicalResultEvaluation,
    hasDeal,
    dealCurrency,
    dealTotalPotentialAmountMin,
    dealTotalPotentialAmountMax,
    sortBy,
    sortDirection,
    sort,
  }: {
    targetId: string,
    xCommercialReservationId: string,
    limit?: number,
    cursor?: (string | null),
    drugEntityId?: (string | null),
    diseaseEntityId?: (string | null),
    organizationEntityId?: (string | null),
    programStatus?: ('active' | 'inactive' | 'unknown' | null),
    organizationRole?: ('originator' | 'collaborator' | 'licensee' | 'licensor' | 'manufacturer' | 'other' | null),
    organizationType?: (string | null),
    organizationCountryRegion?: (string | null),
    modality?: (Array<string> | null),
    innovationType?: (Array<string> | null),
    therapeuticArea?: (Array<string> | null),
    drugCategory?: (Array<string> | null),
    globalPhase?: (DevelopmentPhase | null),
    chinaPhase?: (DevelopmentPhase | null),
    globalPhaseStartedFrom?: (string | null),
    globalPhaseStartedTo?: (string | null),
    chinaPhaseStartedFrom?: (string | null),
    chinaPhaseStartedTo?: (string | null),
    developmentRightsRegion?: (string | null),
    commercializationRightsRegion?: (string | null),
    programTag?: (Array<string> | null),
    milestoneType?: (string | null),
    milestoneFrom?: (string | null),
    milestoneTo?: (string | null),
    hasClinicalResults?: (boolean | null),
    clinicalResultEvaluation?: (TrialResultEvaluation | null),
    hasDeal?: (boolean | null),
    dealCurrency?: (string | null),
    dealTotalPotentialAmountMin?: (number | null),
    dealTotalPotentialAmountMax?: (number | null),
    sortBy?: ('status_date' | 'drug_name' | 'target_name' | 'disease_name' | 'organization_name' | 'modality' | 'mechanism_of_action' | 'phase' | 'status_detail' | 'geography' | 'global_phase' | 'china_phase' | 'global_phase_started_at' | 'china_phase_started_at' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<AgentPageResult_CompetitiveProgramRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/targets/{target_id}/competitive-programs',
      path: {
        'target_id': targetId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'limit': limit,
        'cursor': cursor,
        'drug_entity_id': drugEntityId,
        'disease_entity_id': diseaseEntityId,
        'organization_entity_id': organizationEntityId,
        'program_status': programStatus,
        'organization_role': organizationRole,
        'organization_type': organizationType,
        'organization_country_region': organizationCountryRegion,
        'modality': modality,
        'innovation_type': innovationType,
        'therapeutic_area': therapeuticArea,
        'drug_category': drugCategory,
        'global_phase': globalPhase,
        'china_phase': chinaPhase,
        'global_phase_started_from': globalPhaseStartedFrom,
        'global_phase_started_to': globalPhaseStartedTo,
        'china_phase_started_from': chinaPhaseStartedFrom,
        'china_phase_started_to': chinaPhaseStartedTo,
        'development_rights_region': developmentRightsRegion,
        'commercialization_rights_region': commercializationRightsRegion,
        'program_tag': programTag,
        'milestone_type': milestoneType,
        'milestone_from': milestoneFrom,
        'milestone_to': milestoneTo,
        'has_clinical_results': hasClinicalResults,
        'clinical_result_evaluation': clinicalResultEvaluation,
        'has_deal': hasDeal,
        'deal_currency': dealCurrency,
        'deal_total_potential_amount_min': dealTotalPotentialAmountMin,
        'deal_total_potential_amount_max': dealTotalPotentialAmountMax,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Target Evidence For Agent
   * @returns AgentPageResult_TargetEvidenceRead_ Successful Response
   * @throws ApiError
   */
  public static searchTargetEvidenceForAgentInternalV1DomainTargetsTargetIdEvidenceGet({
    targetId,
    xCommercialReservationId,
    evidenceType,
    direction,
    diseaseEntityId,
    limit = 100,
    cursor,
  }: {
    targetId: string,
    xCommercialReservationId: string,
    evidenceType?: ('genetic_association' | 'expression' | 'functional' | 'translational' | 'biomarker' | 'safety' | null),
    direction?: ('supports' | 'opposes' | 'neutral' | 'unknown' | null),
    diseaseEntityId?: (string | null),
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_TargetEvidenceRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/targets/{target_id}/evidence',
      path: {
        'target_id': targetId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'evidence_type': evidenceType,
        'direction': direction,
        'disease_entity_id': diseaseEntityId,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Compare Target Sar For Agent
   * @returns AgentPageResult_SarActivityRead_ Successful Response
   * @throws ApiError
   */
  public static compareTargetSarForAgentInternalV1DomainTargetsTargetIdSarComparisonGet({
    targetId,
    xCommercialReservationId,
    standardType,
    assayType,
    assayFormat,
    organism,
    cellLine,
    limit = 100,
    cursor,
  }: {
    targetId: string,
    xCommercialReservationId: string,
    standardType?: (string | null),
    assayType?: (string | null),
    assayFormat?: (string | null),
    organism?: (string | null),
    cellLine?: (string | null),
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<AgentPageResult_SarActivityRead_> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/domain/targets/{target_id}/sar-comparison',
      path: {
        'target_id': targetId,
      },
      headers: {
        'X-Commercial-Reservation-ID': xCommercialReservationId,
      },
      query: {
        'standard_type': standardType,
        'assay_type': assayType,
        'assay_format': assayFormat,
        'organism': organism,
        'cell_line': cellLine,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
