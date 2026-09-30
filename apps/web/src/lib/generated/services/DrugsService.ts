/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DrugComparisonResult } from '../models/DrugComparisonResult';
import type { DrugDossierResponse } from '../models/DrugDossierResponse';
import type { DrugProgramSearchResult } from '../models/DrugProgramSearchResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DrugsService {
  /**
   * Compare Drugs
   * @returns DrugComparisonResult Successful Response
   * @throws ApiError
   */
  public static compareDrugsApiV1DrugsComparisonGet({
    drugIds,
  }: {
    drugIds: Array<string>,
  }): CancelablePromise<DrugComparisonResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/drugs/comparison',
      query: {
        'drug_ids': drugIds,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Drug Dossier
   * @returns DrugDossierResponse Successful Response
   * @throws ApiError
   */
  public static getDrugDossierApiV1DrugsDrugIdDossierGet({
    drugId,
    limit = 100,
  }: {
    drugId: string,
    limit?: number,
  }): CancelablePromise<DrugDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/drugs/{drug_id}/dossier',
      path: {
        'drug_id': drugId,
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
   * List Drug Programs
   * @returns DrugProgramSearchResult Successful Response
   * @throws ApiError
   */
  public static listDrugProgramsApiV1DrugsDrugIdProgramsGet({
    drugId,
    limit = 100,
    offset,
  }: {
    drugId: string,
    limit?: number,
    offset?: number,
  }): CancelablePromise<DrugProgramSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/drugs/{drug_id}/programs',
      path: {
        'drug_id': drugId,
      },
      query: {
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
