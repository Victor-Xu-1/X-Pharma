/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicKnowledgePageCoverageRead } from '../models/PublicKnowledgePageCoverageRead';
import type { PublicKnowledgePageDetail } from '../models/PublicKnowledgePageDetail';
import type { PublicKnowledgePageSearchResult } from '../models/PublicKnowledgePageSearchResult';
import type { PublicKnowledgePageSummary } from '../models/PublicKnowledgePageSummary';
import type { PublicKnowledgeVersionDiffRead } from '../models/PublicKnowledgeVersionDiffRead';
import type { PublicKnowledgeVersionSummaryRead } from '../models/PublicKnowledgeVersionSummaryRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class KnowledgeService {
  /**
   * List Knowledge Pages
   * @returns PublicKnowledgePageSummary Successful Response
   * @throws ApiError
   */
  public static listKnowledgePagesApiV1KnowledgePagesGet({
    q,
    pageType,
    limit = 100,
  }: {
    q?: (string | null),
    pageType?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<PublicKnowledgePageSummary>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages',
      query: {
        'q': q,
        'page_type': pageType,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Knowledge Pages
   * @returns PublicKnowledgePageSearchResult Successful Response
   * @throws ApiError
   */
  public static searchKnowledgePagesApiV1KnowledgePagesSearchGet({
    q,
    pageType,
    limit = 50,
    offset,
    sortBy = 'title',
    sortDirection = 'asc',
  }: {
    q?: (string | null),
    pageType?: (string | null),
    limit?: number,
    offset?: number,
    sortBy?: 'title' | 'updated_at',
    sortDirection?: 'asc' | 'desc',
  }): CancelablePromise<PublicKnowledgePageSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages/search',
      query: {
        'q': q,
        'page_type': pageType,
        'limit': limit,
        'offset': offset,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Knowledge Page
   * @returns PublicKnowledgePageDetail Successful Response
   * @throws ApiError
   */
  public static getKnowledgePageApiV1KnowledgePagesPageIdGet({
    pageId,
  }: {
    pageId: string,
  }): CancelablePromise<PublicKnowledgePageDetail> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages/{page_id}',
      path: {
        'page_id': pageId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Knowledge Page Coverage
   * @returns PublicKnowledgePageCoverageRead Successful Response
   * @throws ApiError
   */
  public static getKnowledgePageCoverageApiV1KnowledgePagesPageIdCoverageGet({
    pageId,
  }: {
    pageId: string,
  }): CancelablePromise<PublicKnowledgePageCoverageRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages/{page_id}/coverage',
      path: {
        'page_id': pageId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Knowledge Page Versions
   * @returns PublicKnowledgeVersionSummaryRead Successful Response
   * @throws ApiError
   */
  public static listKnowledgePageVersionsApiV1KnowledgePagesPageIdVersionsGet({
    pageId,
    limit = 50,
  }: {
    pageId: string,
    limit?: number,
  }): CancelablePromise<Array<PublicKnowledgeVersionSummaryRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages/{page_id}/versions',
      path: {
        'page_id': pageId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Knowledge Page Version Diff
   * @returns PublicKnowledgeVersionDiffRead Successful Response
   * @throws ApiError
   */
  public static getKnowledgePageVersionDiffApiV1KnowledgePagesPageIdVersionsVersionNumberDiffGet({
    pageId,
    versionNumber,
    compareTo,
  }: {
    pageId: string,
    versionNumber: number,
    compareTo?: (number | null),
  }): CancelablePromise<PublicKnowledgeVersionDiffRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/knowledge/pages/{page_id}/versions/{version_number}/diff',
      path: {
        'page_id': pageId,
        'version_number': versionNumber,
      },
      query: {
        'compare_to': compareTo,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
