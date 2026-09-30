/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MonitoringAlertRead } from '../models/MonitoringAlertRead';
import type { MonitoringTopicCreate } from '../models/MonitoringTopicCreate';
import type { MonitoringTopicRead } from '../models/MonitoringTopicRead';
import type { MonitoringTopicUpdate } from '../models/MonitoringTopicUpdate';
import type { SavedSearchCreate } from '../models/SavedSearchCreate';
import type { SavedSearchRead } from '../models/SavedSearchRead';
import type { SavedSearchUpdate } from '../models/SavedSearchUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MonitoringService {
  /**
   * List Monitoring Alerts
   * @returns MonitoringAlertRead Successful Response
   * @throws ApiError
   */
  public static listMonitoringAlertsApiV1MonitoringAlertsGet({
    unreadOnly = false,
    limit = 100,
  }: {
    unreadOnly?: boolean,
    limit?: number,
  }): CancelablePromise<Array<MonitoringAlertRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/monitoring/alerts',
      query: {
        'unread_only': unreadOnly,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Mark Monitoring Alert Read
   * @returns void
   * @throws ApiError
   */
  public static markMonitoringAlertReadApiV1MonitoringAlertsAlertIdReadPost({
    alertId,
  }: {
    alertId: string,
  }): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/monitoring/alerts/{alert_id}/read',
      path: {
        'alert_id': alertId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Saved Searches
   * @returns SavedSearchRead Successful Response
   * @throws ApiError
   */
  public static listSavedSearchesApiV1MonitoringSavedSearchesGet(): CancelablePromise<Array<SavedSearchRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/monitoring/saved-searches',
    });
  }
  /**
   * Create Saved Search
   * @returns SavedSearchRead Successful Response
   * @throws ApiError
   */
  public static createSavedSearchApiV1MonitoringSavedSearchesPost({
    requestBody,
  }: {
    requestBody: SavedSearchCreate,
  }): CancelablePromise<SavedSearchRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/monitoring/saved-searches',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Saved Search
   * @returns SavedSearchRead Successful Response
   * @throws ApiError
   */
  public static getSavedSearchApiV1MonitoringSavedSearchesSavedSearchIdGet({
    savedSearchId,
  }: {
    savedSearchId: string,
  }): CancelablePromise<SavedSearchRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/monitoring/saved-searches/{saved_search_id}',
      path: {
        'saved_search_id': savedSearchId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Saved Search
   * @returns SavedSearchRead Successful Response
   * @throws ApiError
   */
  public static updateSavedSearchApiV1MonitoringSavedSearchesSavedSearchIdPatch({
    savedSearchId,
    requestBody,
  }: {
    savedSearchId: string,
    requestBody: SavedSearchUpdate,
  }): CancelablePromise<SavedSearchRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/monitoring/saved-searches/{saved_search_id}',
      path: {
        'saved_search_id': savedSearchId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Monitoring Topics
   * @returns MonitoringTopicRead Successful Response
   * @throws ApiError
   */
  public static listMonitoringTopicsApiV1MonitoringTopicsGet(): CancelablePromise<Array<MonitoringTopicRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/monitoring/topics',
    });
  }
  /**
   * Create Monitoring Topic
   * @returns MonitoringTopicRead Successful Response
   * @throws ApiError
   */
  public static createMonitoringTopicApiV1MonitoringTopicsPost({
    requestBody,
  }: {
    requestBody: MonitoringTopicCreate,
  }): CancelablePromise<MonitoringTopicRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/monitoring/topics',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Monitoring Topic
   * @returns MonitoringTopicRead Successful Response
   * @throws ApiError
   */
  public static updateMonitoringTopicApiV1MonitoringTopicsTopicIdPatch({
    topicId,
    requestBody,
  }: {
    topicId: string,
    requestBody: MonitoringTopicUpdate,
  }): CancelablePromise<MonitoringTopicRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/monitoring/topics/{topic_id}',
      path: {
        'topic_id': topicId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
