/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RecentEntityVisitRead } from '../models/RecentEntityVisitRead';
import type { WebVitalBatchAccepted } from '../models/WebVitalBatchAccepted';
import type { WebVitalBatchCreate } from '../models/WebVitalBatchCreate';
import type { WorkspaceTablePreferenceRead } from '../models/WorkspaceTablePreferenceRead';
import type { WorkspaceTablePreferenceUpdate } from '../models/WorkspaceTablePreferenceUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class WorkspaceService {
  /**
   * List Recent Entities
   * @returns RecentEntityVisitRead Successful Response
   * @throws ApiError
   */
  public static listRecentEntitiesApiV1WorkspaceRecentEntitiesGet({
    limit = 8,
  }: {
    limit?: number,
  }): CancelablePromise<Array<RecentEntityVisitRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/workspace/recent-entities',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Workspace Table Preference
   * @returns WorkspaceTablePreferenceRead Successful Response
   * @throws ApiError
   */
  public static getWorkspaceTablePreferenceApiV1WorkspaceTablePreferencesPreferenceKeyGet({
    preferenceKey,
  }: {
    preferenceKey: 'clinical-trials' | 'deals' | 'entity-search' | 'epidemiology' | 'news-events' | 'patent-families' | 'pipeline' | 'regulatory-events',
  }): CancelablePromise<WorkspaceTablePreferenceRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/workspace/table-preferences/{preference_key}',
      path: {
        'preference_key': preferenceKey,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Workspace Table Preference
   * @returns WorkspaceTablePreferenceRead Successful Response
   * @throws ApiError
   */
  public static updateWorkspaceTablePreferenceApiV1WorkspaceTablePreferencesPreferenceKeyPut({
    preferenceKey,
    requestBody,
  }: {
    preferenceKey: 'clinical-trials' | 'deals' | 'entity-search' | 'epidemiology' | 'news-events' | 'patent-families' | 'pipeline' | 'regulatory-events',
    requestBody: WorkspaceTablePreferenceUpdate,
  }): CancelablePromise<WorkspaceTablePreferenceRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/workspace/table-preferences/{preference_key}',
      path: {
        'preference_key': preferenceKey,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        409: `Preference version conflict`,
        422: `Validation Error`,
      },
    });
  }
  /**
   * Report Workspace Web Vitals
   * @returns WebVitalBatchAccepted Successful Response
   * @throws ApiError
   */
  public static reportWorkspaceWebVitalsApiV1WorkspaceWebVitalsPost({
    requestBody,
  }: {
    requestBody: WebVitalBatchCreate,
  }): CancelablePromise<WebVitalBatchAccepted> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/workspace/web-vitals',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
