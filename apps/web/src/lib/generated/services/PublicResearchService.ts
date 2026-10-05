/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicResearchCoverage } from '../models/PublicResearchCoverage';
import type { PublicResearchQuery } from '../models/PublicResearchQuery';
import type { PublicResearchResponse } from '../models/PublicResearchResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PublicResearchService {
  /**
   * Public Coverage
   * @returns PublicResearchCoverage Successful Response
   * @throws ApiError
   */
  public static publicCoverageApiV1PublicResearchCoverageGet(): CancelablePromise<PublicResearchCoverage> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/public-research/coverage',
    });
  }
  /**
   * Public Research
   * @returns PublicResearchResponse Successful Response
   * @throws ApiError
   */
  public static publicResearchApiV1PublicResearchSearchPost({
    requestBody,
  }: {
    requestBody: PublicResearchQuery,
  }): CancelablePromise<PublicResearchResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/public-research/search',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
