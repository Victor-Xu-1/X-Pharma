/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnvironmentInstallPlanRead } from '../models/EnvironmentInstallPlanRead';
import type { EnvironmentPlanCreate } from '../models/EnvironmentPlanCreate';
import type { EnvironmentRead } from '../models/EnvironmentRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class EnvironmentService {
  /**
   * Read Environment
   * @returns EnvironmentRead Successful Response
   * @throws ApiError
   */
  public static readEnvironmentApiV1EnterpriseEnvironmentGet(): CancelablePromise<EnvironmentRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/environment',
    });
  }
  /**
   * Prepare Environment Installation
   * @returns EnvironmentInstallPlanRead Successful Response
   * @throws ApiError
   */
  public static prepareEnvironmentInstallationApiV1EnterpriseEnvironmentPlansPost({
    requestBody,
  }: {
    requestBody: EnvironmentPlanCreate,
  }): CancelablePromise<EnvironmentInstallPlanRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/environment/plans',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
