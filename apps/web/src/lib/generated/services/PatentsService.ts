/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PatentFamilyRead } from '../models/PatentFamilyRead';
import type { PatentFamilySearchItemRead } from '../models/PatentFamilySearchItemRead';
import type { PatentFamilySearchResult } from '../models/PatentFamilySearchResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PatentsService {
  /**
   * Search Patent Families
   * @returns PatentFamilySearchResult Successful Response
   * @throws ApiError
   */
  public static searchPatentFamiliesApiV1PatentFamiliesGet({
    q,
    entityId,
    applicant,
    legalStatus,
    priorityFrom,
    priorityTo,
    expirationFrom,
    expirationTo,
    limit = 100,
    offset,
    sortBy,
    sortDirection,
    sort,
  }: {
    q?: (string | null),
    entityId?: (string | null),
    applicant?: (string | null),
    legalStatus?: (string | null),
    priorityFrom?: (string | null),
    priorityTo?: (string | null),
    expirationFrom?: (string | null),
    expirationTo?: (string | null),
    limit?: number,
    offset?: number,
    sortBy?: ('priority_date' | 'family_identifier' | 'legal_status' | 'expiration_date' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<PatentFamilySearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/patent-families',
      query: {
        'q': q,
        'entity_id': entityId,
        'applicant': applicant,
        'legal_status': legalStatus,
        'priority_from': priorityFrom,
        'priority_to': priorityTo,
        'expiration_from': expirationFrom,
        'expiration_to': expirationTo,
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
   * Get Patent Family
   * @returns PatentFamilySearchItemRead Successful Response
   * @throws ApiError
   */
  public static getPatentFamilyApiV1PatentFamiliesFamilyIdGet({
    familyId,
  }: {
    familyId: string,
  }): CancelablePromise<PatentFamilySearchItemRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/patent-families/{family_id}',
      path: {
        'family_id': familyId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Patents
   * @returns PatentFamilyRead Successful Response
   * @throws ApiError
   */
  public static searchPatentsApiV1PatentsGet({
    entityId,
    q,
    limit = 100,
  }: {
    entityId?: (string | null),
    q?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<PatentFamilyRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/patents',
      query: {
        'entity_id': entityId,
        'q': q,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
