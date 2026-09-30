/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialDetailRead } from '../models/ClinicalTrialDetailRead';
import type { ClinicalTrialSearchResult } from '../models/ClinicalTrialSearchResult';
import type { DevelopmentPhase } from '../models/DevelopmentPhase';
import type { TrialEntityRole } from '../models/TrialEntityRole';
import type { TrialResultEvaluation } from '../models/TrialResultEvaluation';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TrialsService {
  /**
   * Search Trials
   * @returns ClinicalTrialSearchResult Successful Response
   * @throws ApiError
   */
  public static searchTrialsApiV1TrialsGet({
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
    offset,
    sortBy,
    sortDirection,
    sort,
  }: {
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
    offset?: number,
    sortBy?: ('last_update_posted' | 'registry_id' | 'has_results' | 'result_evaluation' | 'overall_status' | 'enrollment' | 'study_type' | 'acronym' | 'initiation_type' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<ClinicalTrialSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/trials',
      query: {
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
        'offset': offset,
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
   * Get Trial Detail
   * @returns ClinicalTrialDetailRead Successful Response
   * @throws ApiError
   */
  public static getTrialDetailApiV1TrialsTrialIdGet({
    trialId,
  }: {
    trialId: string,
  }): CancelablePromise<ClinicalTrialDetailRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/trials/{trial_id}',
      path: {
        'trial_id': trialId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
