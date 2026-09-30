/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DiseaseDossierResponse } from '../models/DiseaseDossierResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DiseasesService {
  /**
   * Get Disease Dossier
   * @returns DiseaseDossierResponse Successful Response
   * @throws ApiError
   */
  public static getDiseaseDossierApiV1DiseasesDiseaseIdDossierGet({
    diseaseId,
    limit = 100,
  }: {
    diseaseId: string,
    limit?: number,
  }): CancelablePromise<DiseaseDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/diseases/{disease_id}/dossier',
      path: {
        'disease_id': diseaseId,
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
