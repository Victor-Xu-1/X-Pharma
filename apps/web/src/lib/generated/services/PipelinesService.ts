/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompetitiveProgramRead } from '../models/CompetitiveProgramRead';
import type { DevelopmentPhase } from '../models/DevelopmentPhase';
import type { PipelineSearchResult } from '../models/PipelineSearchResult';
import type { TrialResultEvaluation } from '../models/TrialResultEvaluation';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PipelinesService {
  /**
   * Search Pipelines
   * @returns PipelineSearchResult Successful Response
   * @throws ApiError
   */
  public static searchPipelinesApiV1PipelinesGet({
    q,
    modality,
    innovationType,
    therapeuticArea,
    drugCategory,
    programStatus,
    organizationRole,
    organizationType,
    organizationCountryRegion,
    phase,
    geography,
    statusDateFrom,
    statusDateTo,
    drugEntityId,
    targetEntityId,
    targetCombinationKey,
    diseaseEntityId,
    organizationEntityId,
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
    landscapeLimit = 20,
    landscapeStageScope = 'overall',
    landscapeTargetAggregation = 'all',
    resultGrain = 'program',
    limit = 100,
    offset,
  }: {
    q?: (string | null),
    modality?: (Array<string> | null),
    innovationType?: (Array<string> | null),
    therapeuticArea?: (Array<string> | null),
    drugCategory?: (Array<string> | null),
    programStatus?: ('active' | 'inactive' | 'unknown' | null),
    organizationRole?: ('originator' | 'collaborator' | 'licensee' | 'licensor' | 'manufacturer' | 'other' | null),
    organizationType?: (string | null),
    organizationCountryRegion?: (string | null),
    phase?: (DevelopmentPhase | null),
    geography?: (string | null),
    statusDateFrom?: (string | null),
    statusDateTo?: (string | null),
    drugEntityId?: (string | null),
    targetEntityId?: (string | null),
    targetCombinationKey?: (string | null),
    diseaseEntityId?: (string | null),
    organizationEntityId?: (string | null),
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
    landscapeLimit?: number,
    landscapeStageScope?: 'overall' | 'global' | 'china',
    landscapeTargetAggregation?: 'all' | 'primary',
    resultGrain?: 'program' | 'drug',
    limit?: number,
    offset?: number,
  }): CancelablePromise<PipelineSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/pipelines',
      query: {
        'q': q,
        'modality': modality,
        'innovation_type': innovationType,
        'therapeutic_area': therapeuticArea,
        'drug_category': drugCategory,
        'program_status': programStatus,
        'organization_role': organizationRole,
        'organization_type': organizationType,
        'organization_country_region': organizationCountryRegion,
        'phase': phase,
        'geography': geography,
        'status_date_from': statusDateFrom,
        'status_date_to': statusDateTo,
        'drug_entity_id': drugEntityId,
        'target_entity_id': targetEntityId,
        'target_combination_key': targetCombinationKey,
        'disease_entity_id': diseaseEntityId,
        'organization_entity_id': organizationEntityId,
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
        'landscape_limit': landscapeLimit,
        'landscape_stage_scope': landscapeStageScope,
        'landscape_target_aggregation': landscapeTargetAggregation,
        'result_grain': resultGrain,
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Competitive Programs
   * @returns CompetitiveProgramRead Successful Response
   * @throws ApiError
   */
  public static getCompetitiveProgramsApiV1TargetsTargetIdCompetitiveProgramsGet({
    targetId,
    limit = 500,
  }: {
    targetId: string,
    limit?: number,
  }): CancelablePromise<Array<CompetitiveProgramRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/targets/{target_id}/competitive-programs',
      path: {
        'target_id': targetId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
