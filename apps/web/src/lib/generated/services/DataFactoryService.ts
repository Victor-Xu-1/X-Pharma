/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSourceCreate } from '../models/DataSourceCreate';
import type { DataSourceDatasetRead } from '../models/DataSourceDatasetRead';
import type { DataSourceRead } from '../models/DataSourceRead';
import type { DataSourceReadinessRead } from '../models/DataSourceReadinessRead';
import type { DataSourceStateUpdate } from '../models/DataSourceStateUpdate';
import type { DataSourceUpdate } from '../models/DataSourceUpdate';
import type { IngestionCapabilitiesRead } from '../models/IngestionCapabilitiesRead';
import type { IngestionFindingRead } from '../models/IngestionFindingRead';
import type { IngestionRunCancelAcceptedRead } from '../models/IngestionRunCancelAcceptedRead';
import type { IngestionRunCancelRequest } from '../models/IngestionRunCancelRequest';
import type { IngestionRunRead } from '../models/IngestionRunRead';
import type { IngestionRunReplayRequest } from '../models/IngestionRunReplayRequest';
import type { IngestionScanAcceptedRead } from '../models/IngestionScanAcceptedRead';
import type { QuarantineStatus } from '../models/QuarantineStatus';
import type { SearchProjectionStatusRead } from '../models/SearchProjectionStatusRead';
import type { SourceAssetDetailRead } from '../models/SourceAssetDetailRead';
import type { SourceAssetPageRead } from '../models/SourceAssetPageRead';
import type { SourceAssetState } from '../models/SourceAssetState';
import type { SourceVersionPreviewRead } from '../models/SourceVersionPreviewRead';
import type { SourceVersionQuarantineCaseRead } from '../models/SourceVersionQuarantineCaseRead';
import type { SourceVersionQuarantineDecisionAcceptedRead } from '../models/SourceVersionQuarantineDecisionAcceptedRead';
import type { SourceVersionQuarantineDecisionRequest } from '../models/SourceVersionQuarantineDecisionRequest';
import type { SourceVersionReplayAcceptedRead } from '../models/SourceVersionReplayAcceptedRead';
import type { SourceVersionReplayRequest } from '../models/SourceVersionReplayRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DataFactoryService {
  /**
   * List Data Source Datasets
   * @returns DataSourceDatasetRead Successful Response
   * @throws ApiError
   */
  public static listDataSourceDatasetsApiV1AdminDataSourceDatasetsGet(): CancelablePromise<Array<DataSourceDatasetRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/data-source-datasets',
    });
  }
  /**
   * List Data Source Readiness
   * @returns DataSourceReadinessRead Successful Response
   * @throws ApiError
   */
  public static listDataSourceReadinessApiV1AdminDataSourceReadinessGet(): CancelablePromise<Array<DataSourceReadinessRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/data-source-readiness',
    });
  }
  /**
   * List Data Sources
   * @returns DataSourceRead Successful Response
   * @throws ApiError
   */
  public static listDataSourcesApiV1AdminDataSourcesGet(): CancelablePromise<Array<DataSourceRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/data-sources',
    });
  }
  /**
   * Create Data Source
   * @returns DataSourceRead Successful Response
   * @throws ApiError
   */
  public static createDataSourceApiV1AdminDataSourcesPost({
    requestBody,
  }: {
    requestBody: DataSourceCreate,
  }): CancelablePromise<DataSourceRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/data-sources',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Data Source
   * @returns DataSourceRead Successful Response
   * @throws ApiError
   */
  public static updateDataSourceApiV1AdminDataSourcesDataSourceIdPatch({
    dataSourceId,
    requestBody,
  }: {
    dataSourceId: string,
    requestBody: DataSourceUpdate,
  }): CancelablePromise<DataSourceRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/admin/data-sources/{data_source_id}',
      path: {
        'data_source_id': dataSourceId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Trigger Data Source Scan
   * @returns IngestionScanAcceptedRead Successful Response
   * @throws ApiError
   */
  public static triggerDataSourceScanApiV1AdminDataSourcesDataSourceIdScanPost({
    dataSourceId,
  }: {
    dataSourceId: string,
  }): CancelablePromise<IngestionScanAcceptedRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/data-sources/{data_source_id}/scan',
      path: {
        'data_source_id': dataSourceId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Data Source State
   * @returns DataSourceRead Successful Response
   * @throws ApiError
   */
  public static updateDataSourceStateApiV1AdminDataSourcesDataSourceIdStatePatch({
    dataSourceId,
    requestBody,
  }: {
    dataSourceId: string,
    requestBody: DataSourceStateUpdate,
  }): CancelablePromise<DataSourceRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/admin/data-sources/{data_source_id}/state',
      path: {
        'data_source_id': dataSourceId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Ingestion Capabilities
   * @returns IngestionCapabilitiesRead Successful Response
   * @throws ApiError
   */
  public static getIngestionCapabilitiesApiV1AdminIngestionCapabilitiesGet(): CancelablePromise<IngestionCapabilitiesRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/ingestion-capabilities',
    });
  }
  /**
   * List Ingestion Runs
   * @returns IngestionRunRead Successful Response
   * @throws ApiError
   */
  public static listIngestionRunsApiV1AdminIngestionRunsGet({
    dataSourceId,
    limit = 100,
  }: {
    dataSourceId?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<IngestionRunRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/ingestion-runs',
      query: {
        'data_source_id': dataSourceId,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Cancel Ingestion Run
   * @returns IngestionRunCancelAcceptedRead Successful Response
   * @throws ApiError
   */
  public static cancelIngestionRunApiV1AdminIngestionRunsRunIdCancelPost({
    runId,
    requestBody,
  }: {
    runId: string,
    requestBody: IngestionRunCancelRequest,
  }): CancelablePromise<IngestionRunCancelAcceptedRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/ingestion-runs/{run_id}/cancel',
      path: {
        'run_id': runId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Ingestion Findings
   * @returns IngestionFindingRead Successful Response
   * @throws ApiError
   */
  public static listIngestionFindingsApiV1AdminIngestionRunsRunIdFindingsGet({
    runId,
  }: {
    runId: string,
  }): CancelablePromise<Array<IngestionFindingRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/ingestion-runs/{run_id}/findings',
      path: {
        'run_id': runId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Replay Ingestion Run
   * @returns IngestionScanAcceptedRead Successful Response
   * @throws ApiError
   */
  public static replayIngestionRunApiV1AdminIngestionRunsRunIdReplayPost({
    runId,
    requestBody,
  }: {
    runId: string,
    requestBody: IngestionRunReplayRequest,
  }): CancelablePromise<IngestionScanAcceptedRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/ingestion-runs/{run_id}/replay',
      path: {
        'run_id': runId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Source Version Quarantine Cases
   * @returns SourceVersionQuarantineCaseRead Successful Response
   * @throws ApiError
   */
  public static listSourceVersionQuarantineCasesApiV1AdminQuarantineCasesGet({
    status,
    limit = 100,
  }: {
    status?: (QuarantineStatus | null),
    limit?: number,
  }): CancelablePromise<Array<SourceVersionQuarantineCaseRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/quarantine-cases',
      query: {
        'status': status,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Source Version Quarantine Case
   * @returns SourceVersionQuarantineCaseRead Successful Response
   * @throws ApiError
   */
  public static getSourceVersionQuarantineCaseApiV1AdminQuarantineCasesVersionIdGet({
    versionId,
  }: {
    versionId: string,
  }): CancelablePromise<SourceVersionQuarantineCaseRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/quarantine-cases/{version_id}',
      path: {
        'version_id': versionId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Decide Source Version Quarantine Case
   * @returns SourceVersionQuarantineDecisionAcceptedRead Successful Response
   * @throws ApiError
   */
  public static decideSourceVersionQuarantineCaseApiV1AdminQuarantineCasesVersionIdDecisionsPost({
    versionId,
    requestBody,
  }: {
    versionId: string,
    requestBody: SourceVersionQuarantineDecisionRequest,
  }): CancelablePromise<SourceVersionQuarantineDecisionAcceptedRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/quarantine-cases/{version_id}/decisions',
      path: {
        'version_id': versionId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Projection Status
   * @returns SearchProjectionStatusRead Successful Response
   * @throws ApiError
   */
  public static searchProjectionStatusApiV1AdminSearchStatusGet(): CancelablePromise<SearchProjectionStatusRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/search/status',
    });
  }
  /**
   * List Source Assets
   * @returns SourceAssetPageRead Successful Response
   * @throws ApiError
   */
  public static listSourceAssetsApiV1AdminSourceAssetsGet({
    dataSourceId,
    state,
    limit = 200,
    offset,
  }: {
    dataSourceId?: (string | null),
    state?: (SourceAssetState | null),
    limit?: number,
    offset?: number,
  }): CancelablePromise<SourceAssetPageRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/source-assets',
      query: {
        'data_source_id': dataSourceId,
        'state': state,
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Source Asset Detail
   * @returns SourceAssetDetailRead Successful Response
   * @throws ApiError
   */
  public static getSourceAssetDetailApiV1AdminSourceAssetsAssetIdGet({
    assetId,
  }: {
    assetId: string,
  }): CancelablePromise<SourceAssetDetailRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/source-assets/{asset_id}',
      path: {
        'asset_id': assetId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Source Version Preview
   * @returns SourceVersionPreviewRead Successful Response
   * @throws ApiError
   */
  public static getSourceVersionPreviewApiV1AdminSourceVersionsVersionIdPreviewGet({
    versionId,
    maxChars = 20000,
  }: {
    versionId: string,
    maxChars?: number,
  }): CancelablePromise<SourceVersionPreviewRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/admin/source-versions/{version_id}/preview',
      path: {
        'version_id': versionId,
      },
      query: {
        'max_chars': maxChars,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Replay Source Version
   * @returns SourceVersionReplayAcceptedRead Successful Response
   * @throws ApiError
   */
  public static replaySourceVersionApiV1AdminSourceVersionsVersionIdReplayPost({
    versionId,
    requestBody,
  }: {
    versionId: string,
    requestBody: SourceVersionReplayRequest,
  }): CancelablePromise<SourceVersionReplayAcceptedRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/source-versions/{version_id}/replay',
      path: {
        'version_id': versionId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
