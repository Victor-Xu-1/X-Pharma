/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewsEventSearchItemRead } from '../models/NewsEventSearchItemRead';
import type { NewsEventSearchResult } from '../models/NewsEventSearchResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class NewsService {
  /**
   * Search News Events
   * @returns NewsEventSearchResult Successful Response
   * @throws ApiError
   */
  public static searchNewsEventsApiV1NewsEventsGet({
    q,
    entityId,
    eventType,
    publisher,
    language,
    venue,
    contentScope,
    publishedFrom,
    publishedTo,
    limit = 100,
    offset,
    sortBy,
    sortDirection,
    sort,
  }: {
    q?: (string | null),
    entityId?: (string | null),
    eventType?: (string | null),
    publisher?: (string | null),
    language?: (string | null),
    venue?: (string | null),
    contentScope?: (string | null),
    publishedFrom?: (string | null),
    publishedTo?: (string | null),
    limit?: number,
    offset?: number,
    sortBy?: ('published_at' | 'title' | 'event_type' | 'publisher' | 'venue' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<NewsEventSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/news-events',
      query: {
        'q': q,
        'entity_id': entityId,
        'event_type': eventType,
        'publisher': publisher,
        'language': language,
        'venue': venue,
        'content_scope': contentScope,
        'published_from': publishedFrom,
        'published_to': publishedTo,
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
   * Get News Event
   * @returns NewsEventSearchItemRead Successful Response
   * @throws ApiError
   */
  public static getNewsEventApiV1NewsEventsEventIdGet({
    eventId,
  }: {
    eventId: string,
  }): CancelablePromise<NewsEventSearchItemRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/news-events/{event_id}',
      path: {
        'event_id': eventId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
