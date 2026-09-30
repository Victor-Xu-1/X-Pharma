/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TargetDossierResponse } from '../models/TargetDossierResponse';
import type { TargetProfileResponse } from '../models/TargetProfileResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TargetsService {
  /**
   * Get Target Dossier
   * @returns TargetDossierResponse Successful Response
   * @throws ApiError
   */
  public static getTargetDossierApiV1TargetsTargetIdDossierGet({
    targetId,
    limit = 100,
  }: {
    targetId: string,
    limit?: number,
  }): CancelablePromise<TargetDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/targets/{target_id}/dossier',
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
  /**
   * Get Target Profile
   * @returns TargetProfileResponse Successful Response
   * @throws ApiError
   */
  public static getTargetProfileApiV1TargetsTargetIdProfileGet({
    targetId,
  }: {
    targetId: string,
  }): CancelablePromise<TargetProfileResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/targets/{target_id}/profile',
      path: {
        'target_id': targetId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
