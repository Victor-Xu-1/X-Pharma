/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialRead } from '../models/ClinicalTrialRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ClinicalTrialsService {
  /**
   * Search Clinical Trials
   * @returns ClinicalTrialRead Successful Response
   * @throws ApiError
   */
  public static searchClinicalTrialsApiV1ClinicalTrialsGet({
    entityId,
    q,
    hasResults,
    limit = 100,
  }: {
    entityId?: (string | null),
    q?: (string | null),
    hasResults?: (boolean | null),
    limit?: number,
  }): CancelablePromise<Array<ClinicalTrialRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/clinical-trials',
      query: {
        'entity_id': entityId,
        'q': q,
        'has_results': hasResults,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
