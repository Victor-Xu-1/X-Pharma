/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CommercialAccessRead } from '../models/CommercialAccessRead';
import type { CommercialEstimateRead } from '../models/CommercialEstimateRead';
import type { CommercialEstimateRequest } from '../models/CommercialEstimateRequest';
import type { CommercialReleaseRequest } from '../models/CommercialReleaseRequest';
import type { CommercialReservationRead } from '../models/CommercialReservationRead';
import type { CommercialReserveRequest } from '../models/CommercialReserveRequest';
import type { CommercialSettlementRequest } from '../models/CommercialSettlementRequest';
import type { CommercialUsageSummaryRead } from '../models/CommercialUsageSummaryRead';
import type { DataExportChunkRead } from '../models/DataExportChunkRead';
import type { DataExportCreate } from '../models/DataExportCreate';
import type { DataExportRead } from '../models/DataExportRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class InternalCommercialService {
  /**
   * Commercial Access
   * @returns CommercialAccessRead Successful Response
   * @throws ApiError
   */
  public static commercialAccessInternalV1CommercialAccessGet(): CancelablePromise<CommercialAccessRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/commercial/access',
    });
  }
  /**
   * Estimate Commercial Usage
   * @returns CommercialEstimateRead Successful Response
   * @throws ApiError
   */
  public static estimateCommercialUsageInternalV1CommercialEstimatePost({
    requestBody,
  }: {
    requestBody: CommercialEstimateRequest,
  }): CancelablePromise<CommercialEstimateRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/commercial/estimate',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Reserve Commercial Usage
   * @returns CommercialReservationRead Successful Response
   * @throws ApiError
   */
  public static reserveCommercialUsageInternalV1CommercialReservationsPost({
    requestBody,
  }: {
    requestBody: CommercialReserveRequest,
  }): CancelablePromise<CommercialReservationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/commercial/reservations',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Release Commercial Usage
   * @returns CommercialReservationRead Successful Response
   * @throws ApiError
   */
  public static releaseCommercialUsageInternalV1CommercialReservationsReservationIdReleasePost({
    reservationId,
    requestBody,
  }: {
    reservationId: string,
    requestBody: CommercialReleaseRequest,
  }): CancelablePromise<CommercialReservationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/commercial/reservations/{reservation_id}/release',
      path: {
        'reservation_id': reservationId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Settle Commercial Usage
   * @returns CommercialReservationRead Successful Response
   * @throws ApiError
   */
  public static settleCommercialUsageInternalV1CommercialReservationsReservationIdSettlePost({
    reservationId,
    requestBody,
  }: {
    reservationId: string,
    requestBody: CommercialSettlementRequest,
  }): CancelablePromise<CommercialReservationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/commercial/reservations/{reservation_id}/settle',
      path: {
        'reservation_id': reservationId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Commercial Usage Summary
   * @returns CommercialUsageSummaryRead Successful Response
   * @throws ApiError
   */
  public static commercialUsageSummaryInternalV1CommercialUsageSummaryGet(): CancelablePromise<CommercialUsageSummaryRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/commercial/usage-summary',
    });
  }
  /**
   * Create Data Export
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static createDataExportInternalV1ExportsPost({
    requestBody,
  }: {
    requestBody: DataExportCreate,
  }): CancelablePromise<DataExportRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/exports',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Read Data Export
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static readDataExportInternalV1ExportsJobIdGet({
    jobId,
  }: {
    jobId: string,
  }): CancelablePromise<DataExportRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/exports/{job_id}',
      path: {
        'job_id': jobId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Cancel Data Export
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static cancelDataExportInternalV1ExportsJobIdCancelPost({
    jobId,
  }: {
    jobId: string,
  }): CancelablePromise<DataExportRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/internal/v1/exports/{job_id}/cancel',
      path: {
        'job_id': jobId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Read Data Export Chunk
   * @returns DataExportChunkRead Successful Response
   * @throws ApiError
   */
  public static readDataExportChunkInternalV1ExportsJobIdChunksGet({
    jobId,
    limit = 100,
    cursor,
  }: {
    jobId: string,
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<DataExportChunkRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/internal/v1/exports/{job_id}/chunks',
      path: {
        'job_id': jobId,
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
}
