/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompanyDossierResponse } from '../models/CompanyDossierResponse';
import type { CompanyTimelineResult } from '../models/CompanyTimelineResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CompaniesService {
  /**
   * Get Company Dossier
   * @returns CompanyDossierResponse Successful Response
   * @throws ApiError
   */
  public static getCompanyDossierApiV1CompaniesCompanyIdDossierGet({
    companyId,
    limit = 100,
  }: {
    companyId: string,
    limit?: number,
  }): CancelablePromise<CompanyDossierResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/companies/{company_id}/dossier',
      path: {
        'company_id': companyId,
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
   * Get Company Timeline
   * @returns CompanyTimelineResult Successful Response
   * @throws ApiError
   */
  public static getCompanyTimelineApiV1CompaniesCompanyIdTimelineGet({
    companyId,
    limit = 100,
    offset,
  }: {
    companyId: string,
    limit?: number,
    offset?: number,
  }): CancelablePromise<CompanyTimelineResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/companies/{company_id}/timeline',
      path: {
        'company_id': companyId,
      },
      query: {
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
