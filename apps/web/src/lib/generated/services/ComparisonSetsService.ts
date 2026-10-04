/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ComparisonSetCatalogRead } from '../models/ComparisonSetCatalogRead';
import type { ComparisonSetCreate } from '../models/ComparisonSetCreate';
import type { ComparisonSetDetailRead } from '../models/ComparisonSetDetailRead';
import type { ComparisonSetMemberCreate } from '../models/ComparisonSetMemberCreate';
import type { ComparisonSetMemberRemove } from '../models/ComparisonSetMemberRemove';
import type { ComparisonSetMembersAdd } from '../models/ComparisonSetMembersAdd';
import type { ComparisonSetSummaryRead } from '../models/ComparisonSetSummaryRead';
import type { ComparisonSetUpdate } from '../models/ComparisonSetUpdate';
import type { ComparisonSetVersionRead } from '../models/ComparisonSetVersionRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ComparisonSetsService {
  /**
   * List Comparison Sets
   * @returns ComparisonSetSummaryRead Successful Response
   * @throws ApiError
   */
  public static listComparisonSetsApiV1ComparisonSetsGet(): CancelablePromise<Array<ComparisonSetSummaryRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/comparison-sets',
    });
  }
  /**
   * Create Comparison Set
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static createComparisonSetApiV1ComparisonSetsPost({
    requestBody,
  }: {
    requestBody: ComparisonSetCreate,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/comparison-sets',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Comparison Set Catalog
   * @returns ComparisonSetCatalogRead Successful Response
   * @throws ApiError
   */
  public static comparisonSetCatalogApiV1ComparisonSetsCatalogGet({
    q = '',
    limit = 25,
    offset,
    editableOnly = false,
  }: {
    q?: string,
    limit?: number,
    offset?: number,
    editableOnly?: boolean,
  }): CancelablePromise<ComparisonSetCatalogRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/comparison-sets/catalog',
      query: {
        'q': q,
        'limit': limit,
        'offset': offset,
        'editable_only': editableOnly,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Comparison Set
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static getComparisonSetApiV1ComparisonSetsComparisonSetIdGet({
    comparisonSetId,
  }: {
    comparisonSetId: string,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/comparison-sets/{comparison_set_id}',
      path: {
        'comparison_set_id': comparisonSetId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Comparison Set
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static updateComparisonSetApiV1ComparisonSetsComparisonSetIdPatch({
    comparisonSetId,
    requestBody,
  }: {
    comparisonSetId: string,
    requestBody: ComparisonSetUpdate,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/comparison-sets/{comparison_set_id}',
      path: {
        'comparison_set_id': comparisonSetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Add Comparison Set Member
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static addComparisonSetMemberApiV1ComparisonSetsComparisonSetIdMembersPost({
    comparisonSetId,
    requestBody,
  }: {
    comparisonSetId: string,
    requestBody: ComparisonSetMemberCreate,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/comparison-sets/{comparison_set_id}/members',
      path: {
        'comparison_set_id': comparisonSetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Add Comparison Set Members
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static addComparisonSetMembersApiV1ComparisonSetsComparisonSetIdMembersBatchPost({
    comparisonSetId,
    requestBody,
  }: {
    comparisonSetId: string,
    requestBody: ComparisonSetMembersAdd,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/comparison-sets/{comparison_set_id}/members/batch',
      path: {
        'comparison_set_id': comparisonSetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Remove Comparison Set Member
   * @returns ComparisonSetDetailRead Successful Response
   * @throws ApiError
   */
  public static removeComparisonSetMemberApiV1ComparisonSetsComparisonSetIdMembersEntityIdRemovePost({
    comparisonSetId,
    entityId,
    requestBody,
  }: {
    comparisonSetId: string,
    entityId: string,
    requestBody: ComparisonSetMemberRemove,
  }): CancelablePromise<ComparisonSetDetailRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/comparison-sets/{comparison_set_id}/members/{entity_id}/remove',
      path: {
        'comparison_set_id': comparisonSetId,
        'entity_id': entityId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Comparison Set Versions
   * @returns ComparisonSetVersionRead Successful Response
   * @throws ApiError
   */
  public static listComparisonSetVersionsApiV1ComparisonSetsComparisonSetIdVersionsGet({
    comparisonSetId,
    limit = 50,
    beforeVersion,
  }: {
    comparisonSetId: string,
    limit?: number,
    beforeVersion?: (number | null),
  }): CancelablePromise<Array<ComparisonSetVersionRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/comparison-sets/{comparison_set_id}/versions',
      path: {
        'comparison_set_id': comparisonSetId,
      },
      query: {
        'limit': limit,
        'before_version': beforeVersion,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
