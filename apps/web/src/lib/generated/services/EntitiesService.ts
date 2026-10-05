/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityCreate } from '../models/EntityCreate';
import type { EntityDossierResponse } from '../models/EntityDossierResponse';
import type { EntityRead } from '../models/EntityRead';
import type { EntitySuggestionResult } from '../models/EntitySuggestionResult';
import type { EntityType } from '../models/EntityType';
import type { ReviewStatus } from '../models/ReviewStatus';
import type { SearchResult } from '../models/SearchResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class EntitiesService {
  /**
   * Search Entities
   * @returns SearchResult Successful Response
   * @throws ApiError
   */
  public static searchEntitiesApiV1EntitiesGet({
    q,
    entityType,
    reviewStatus,
    limit = 25,
    offset,
    sortBy,
    sortDirection,
    entityTypes,
    sort,
    includeRelated = false,
  }: {
    q?: (string | null),
    entityType?: (EntityType | null),
    reviewStatus?: (ReviewStatus | null),
    limit?: number,
    offset?: number,
    sortBy?: ('relevance' | 'name' | 'entity_type' | 'updated_at' | null),
    sortDirection?: ('asc' | 'desc' | null),
    entityTypes?: (Array<EntityType> | null),
    sort?: (Array<string> | null),
    includeRelated?: boolean,
  }): CancelablePromise<SearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/entities',
      query: {
        'q': q,
        'entity_type': entityType,
        'review_status': reviewStatus,
        'limit': limit,
        'offset': offset,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'entity_types': entityTypes,
        'sort': sort,
        'include_related': includeRelated,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Create Entity
   * @returns EntityRead Successful Response
   * @throws ApiError
   */
  public static createEntityApiV1EntitiesPost({
    requestBody,
  }: {
    requestBody: EntityCreate,
  }): CancelablePromise<EntityRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/entities',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Suggest Entities
   * @returns EntitySuggestionResult Successful Response
   * @throws ApiError
   */
  public static suggestEntitiesApiV1EntitiesSuggestionsGet({
    q,
    entityType,
    limit = 10,
    entityTypes,
  }: {
    q: string,
    entityType?: (EntityType | null),
    limit?: number,
    entityTypes?: (Array<EntityType> | null),
  }): CancelablePromise<EntitySuggestionResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/entities/suggestions',
      query: {
        'q': q,
        'entity_type': entityType,
        'limit': limit,
        'entity_types': entityTypes,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Entity
   * @returns EntityRead Successful Response
   * @throws ApiError
   */
  public static getEntityApiV1EntitiesEntityIdGet({
    entityId,
  }: {
    entityId: string,
  }): CancelablePromise<EntityRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/entities/{entity_id}',
      path: {
        'entity_id': entityId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Entity Dossier
   * @returns EntityDossierResponse Successful Response
   * @throws ApiError
   */
  public static getEntityDossierApiV1EntitiesEntityIdDossierGet({
    entityId,
    limit = 50,
  }: {
    entityId: string,
    limit?: number,
  }): CancelablePromise<EntityDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/entities/{entity_id}/dossier',
      path: {
        'entity_id': entityId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
