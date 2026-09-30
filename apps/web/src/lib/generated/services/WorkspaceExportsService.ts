/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WorkspaceDomainExportCreate } from '../models/WorkspaceDomainExportCreate';
import type { WorkspaceExportCreate } from '../models/WorkspaceExportCreate';
import type { WorkspaceExportPolicyRead } from '../models/WorkspaceExportPolicyRead';
import type { WorkspaceExportPolicyUpsert } from '../models/WorkspaceExportPolicyUpsert';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class WorkspaceExportsService {
  /**
   * Configure Workspace Export Policy
   * @returns WorkspaceExportPolicyRead Successful Response
   * @throws ApiError
   */
  public static configureWorkspaceExportPolicyApiV1AdminWorkspaceExportPolicyPost({
    requestBody,
  }: {
    requestBody: WorkspaceExportPolicyUpsert,
  }): CancelablePromise<WorkspaceExportPolicyRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/admin/workspace-export-policy',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Export Comparison Set
   * @returns any Successful Response
   * @throws ApiError
   */
  public static exportComparisonSetApiV1ComparisonSetsComparisonSetIdExportPost({
    comparisonSetId,
    requestBody,
  }: {
    comparisonSetId: string,
    requestBody: WorkspaceExportCreate,
  }): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/comparison-sets/{comparison_set_id}/export',
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
   * Export Workspace Domain Query
   * @returns any Successful Response
   * @throws ApiError
   */
  public static exportWorkspaceDomainQueryApiV1WorkspaceDomainExportsPost({
    requestBody,
  }: {
    requestBody: WorkspaceDomainExportCreate,
  }): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/workspace/domain-exports',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Workspace Export Policy
   * @returns WorkspaceExportPolicyRead Successful Response
   * @throws ApiError
   */
  public static getWorkspaceExportPolicyApiV1WorkspaceExportPolicyGet(): CancelablePromise<WorkspaceExportPolicyRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/workspace/export-policy',
    });
  }
}
