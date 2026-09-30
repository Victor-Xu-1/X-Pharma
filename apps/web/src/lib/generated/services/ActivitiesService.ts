/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BioactivityRead } from '../models/BioactivityRead';
import type { SarComparisonResult } from '../models/SarComparisonResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ActivitiesService {
  /**
   * Get Bioactivities
   * @returns BioactivityRead Successful Response
   * @throws ApiError
   */
  public static getBioactivitiesApiV1TargetsTargetIdBioactivitiesGet({
    targetId,
    standardType,
    limit = 200,
    offset,
  }: {
    targetId: string,
    standardType?: (string | null),
    limit?: number,
    offset?: number,
  }): CancelablePromise<Array<BioactivityRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/targets/{target_id}/bioactivities',
      path: {
        'target_id': targetId,
      },
      query: {
        'standard_type': standardType,
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Compare Target Sar
   * @returns SarComparisonResult Successful Response
   * @throws ApiError
   */
  public static compareTargetSarApiV1TargetsTargetIdSarComparisonGet({
    targetId,
    standardType,
    assayType,
    assayFormat,
    organism,
    cellLine,
    limit = 100,
    offset,
  }: {
    targetId: string,
    standardType?: (string | null),
    assayType?: (string | null),
    assayFormat?: (string | null),
    organism?: (string | null),
    cellLine?: (string | null),
    limit?: number,
    offset?: number,
  }): CancelablePromise<SarComparisonResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/targets/{target_id}/sar-comparison',
      path: {
        'target_id': targetId,
      },
      query: {
        'standard_type': standardType,
        'assay_type': assayType,
        'assay_format': assayFormat,
        'organism': organism,
        'cell_line': cellLine,
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
