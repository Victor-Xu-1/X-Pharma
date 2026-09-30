/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegulatoryDesignationType } from '../models/RegulatoryDesignationType';
import type { RegulatoryEventRead } from '../models/RegulatoryEventRead';
import type { RegulatoryEventSearchItemRead } from '../models/RegulatoryEventSearchItemRead';
import type { RegulatoryEventSearchResult } from '../models/RegulatoryEventSearchResult';
import type { RegulatoryLabelChangeType } from '../models/RegulatoryLabelChangeType';
import type { RegulatorySafetySeverity } from '../models/RegulatorySafetySeverity';
import type { RegulatorySafetySignalType } from '../models/RegulatorySafetySignalType';
import type { RegulatorySafetyStatus } from '../models/RegulatorySafetyStatus';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class RegulatoryService {
  /**
   * Search Regulatory Event Timeline
   * @returns RegulatoryEventSearchResult Successful Response
   * @throws ApiError
   */
  public static searchRegulatoryEventTimelineApiV1RegulatoryEventTimelineGet({
    q,
    agency,
    jurisdiction,
    eventType,
    status,
    designationType,
    labelChangeType,
    hasBoxedWarning,
    safetySignalType,
    safetySeverity,
    safetyStatus,
    decisionFrom,
    decisionTo,
    sourceUpdatedFrom,
    sourceUpdatedTo,
    limit = 100,
    offset,
    sortBy,
    sortDirection,
    sort,
  }: {
    q?: (string | null),
    agency?: (string | null),
    jurisdiction?: (string | null),
    eventType?: (string | null),
    status?: (string | null),
    designationType?: (RegulatoryDesignationType | null),
    labelChangeType?: (RegulatoryLabelChangeType | null),
    hasBoxedWarning?: (boolean | null),
    safetySignalType?: (RegulatorySafetySignalType | null),
    safetySeverity?: (RegulatorySafetySeverity | null),
    safetyStatus?: (RegulatorySafetyStatus | null),
    decisionFrom?: (string | null),
    decisionTo?: (string | null),
    sourceUpdatedFrom?: (string | null),
    sourceUpdatedTo?: (string | null),
    limit?: number,
    offset?: number,
    sortBy?: ('decision_date' | 'title' | 'agency' | 'jurisdiction' | 'event_type' | 'status' | 'subject' | 'source_updated_at' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<RegulatoryEventSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/regulatory-event-timeline',
      query: {
        'q': q,
        'agency': agency,
        'jurisdiction': jurisdiction,
        'event_type': eventType,
        'status': status,
        'designation_type': designationType,
        'label_change_type': labelChangeType,
        'has_boxed_warning': hasBoxedWarning,
        'safety_signal_type': safetySignalType,
        'safety_severity': safetySeverity,
        'safety_status': safetyStatus,
        'decision_from': decisionFrom,
        'decision_to': decisionTo,
        'source_updated_from': sourceUpdatedFrom,
        'source_updated_to': sourceUpdatedTo,
        'limit': limit,
        'offset': offset,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Regulatory Event Timeline Item
   * @returns RegulatoryEventSearchItemRead Successful Response
   * @throws ApiError
   */
  public static getRegulatoryEventTimelineItemApiV1RegulatoryEventTimelineEventIdGet({
    eventId,
  }: {
    eventId: string,
  }): CancelablePromise<RegulatoryEventSearchItemRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/regulatory-event-timeline/{event_id}',
      path: {
        'event_id': eventId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Regulatory Events
   * @returns RegulatoryEventRead Successful Response
   * @throws ApiError
   */
  public static searchRegulatoryEventsApiV1RegulatoryEventsGet({
    entityId,
    q,
    agency,
    limit = 100,
  }: {
    entityId?: (string | null),
    q?: (string | null),
    agency?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<RegulatoryEventRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/regulatory-events',
      query: {
        'entity_id': entityId,
        'q': q,
        'agency': agency,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
