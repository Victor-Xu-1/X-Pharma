/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnterpriseApiKeyCatalogRead } from '../models/EnterpriseApiKeyCatalogRead';
import type { EnterpriseApiKeyCreate } from '../models/EnterpriseApiKeyCreate';
import type { EnterpriseApiKeyRead } from '../models/EnterpriseApiKeyRead';
import type { EnterpriseApiKeyRevoke } from '../models/EnterpriseApiKeyRevoke';
import type { EnterpriseApiKeyRotate } from '../models/EnterpriseApiKeyRotate';
import type { EnterpriseApiKeySecretRead } from '../models/EnterpriseApiKeySecretRead';
import type { EnterpriseAuditPageRead } from '../models/EnterpriseAuditPageRead';
import type { EnterpriseDatasetRead } from '../models/EnterpriseDatasetRead';
import type { EnterpriseDatasetStatusUpdate } from '../models/EnterpriseDatasetStatusUpdate';
import type { EnterpriseLLMProviderCreate } from '../models/EnterpriseLLMProviderCreate';
import type { EnterpriseLLMProviderPrimaryUpdate } from '../models/EnterpriseLLMProviderPrimaryUpdate';
import type { EnterpriseLLMProviderRead } from '../models/EnterpriseLLMProviderRead';
import type { EnterpriseLLMProviderUpdate } from '../models/EnterpriseLLMProviderUpdate';
import type { EnterpriseOverviewRead } from '../models/EnterpriseOverviewRead';
import type { EnterpriseSessionRead } from '../models/EnterpriseSessionRead';
import type { EnterpriseSessionRevoke } from '../models/EnterpriseSessionRevoke';
import type { EnterpriseUserCreate } from '../models/EnterpriseUserCreate';
import type { EnterpriseUserRead } from '../models/EnterpriseUserRead';
import type { EnterpriseUserRoleUpdate } from '../models/EnterpriseUserRoleUpdate';
import type { EnterpriseUserStatusUpdate } from '../models/EnterpriseUserStatusUpdate';
import type { InvitationCreate } from '../models/InvitationCreate';
import type { InvitationIssued } from '../models/InvitationIssued';
import type { InvitationRead } from '../models/InvitationRead';
import type { PlatformOperationsRead } from '../models/PlatformOperationsRead';
import type { UserGroupCreate } from '../models/UserGroupCreate';
import type { UserGroupMembershipUpdate } from '../models/UserGroupMembershipUpdate';
import type { UserGroupRead } from '../models/UserGroupRead';
import type { UserGroupUpdate } from '../models/UserGroupUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class EnterpriseService {
  /**
   * List Account Invitations
   * @returns InvitationRead Successful Response
   * @throws ApiError
   */
  public static listAccountInvitationsApiV1EnterpriseAccountInvitationsGet(): CancelablePromise<Array<InvitationRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/account-invitations',
    });
  }
  /**
   * Create Account Invitation
   * @returns InvitationIssued Successful Response
   * @throws ApiError
   */
  public static createAccountInvitationApiV1EnterpriseAccountInvitationsPost({
    requestBody,
  }: {
    requestBody: InvitationCreate,
  }): CancelablePromise<InvitationIssued> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/account-invitations',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Revoke Account Invitation
   * @returns void
   * @throws ApiError
   */
  public static revokeAccountInvitationApiV1EnterpriseAccountInvitationsInvitationIdDelete({
    invitationId,
  }: {
    invitationId: string,
  }): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/v1/enterprise/account-invitations/{invitation_id}',
      path: {
        'invitation_id': invitationId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Api Keys
   * @returns EnterpriseApiKeyCatalogRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseApiKeysApiV1EnterpriseApiKeysGet({
    limit = 200,
  }: {
    limit?: number,
  }): CancelablePromise<EnterpriseApiKeyCatalogRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/api-keys',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Create Enterprise Api Key
   * @returns EnterpriseApiKeySecretRead Successful Response
   * @throws ApiError
   */
  public static createEnterpriseApiKeyApiV1EnterpriseApiKeysPost({
    requestBody,
  }: {
    requestBody: EnterpriseApiKeyCreate,
  }): CancelablePromise<EnterpriseApiKeySecretRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/api-keys',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Revoke Enterprise Api Key
   * @returns EnterpriseApiKeyRead Successful Response
   * @throws ApiError
   */
  public static revokeEnterpriseApiKeyApiV1EnterpriseApiKeysKeyIdRevokePost({
    keyId,
    requestBody,
  }: {
    keyId: string,
    requestBody: EnterpriseApiKeyRevoke,
  }): CancelablePromise<EnterpriseApiKeyRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/api-keys/{key_id}/revoke',
      path: {
        'key_id': keyId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Rotate Enterprise Api Key
   * @returns EnterpriseApiKeySecretRead Successful Response
   * @throws ApiError
   */
  public static rotateEnterpriseApiKeyApiV1EnterpriseApiKeysKeyIdRotatePost({
    keyId,
    requestBody,
  }: {
    keyId: string,
    requestBody: EnterpriseApiKeyRotate,
  }): CancelablePromise<EnterpriseApiKeySecretRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/api-keys/{key_id}/rotate',
      path: {
        'key_id': keyId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Audit Events
   * @returns EnterpriseAuditPageRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseAuditEventsApiV1EnterpriseAuditEventsGet({
    limit = 100,
    cursor,
    action,
    outcome,
    actorType,
  }: {
    limit?: number,
    cursor?: (string | null),
    action?: (string | null),
    outcome?: (string | null),
    actorType?: ('agent' | 'api_key' | 'user' | null),
  }): CancelablePromise<EnterpriseAuditPageRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/audit-events',
      query: {
        'limit': limit,
        'cursor': cursor,
        'action': action,
        'outcome': outcome,
        'actor_type': actorType,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Datasets
   * @returns EnterpriseDatasetRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseDatasetsApiV1EnterpriseDatasetsGet(): CancelablePromise<Array<EnterpriseDatasetRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/datasets',
    });
  }
  /**
   * Update Enterprise Dataset Status
   * @returns EnterpriseDatasetRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseDatasetStatusApiV1EnterpriseDatasetsDatasetIdStatusPost({
    datasetId,
    requestBody,
  }: {
    datasetId: string,
    requestBody: EnterpriseDatasetStatusUpdate,
  }): CancelablePromise<EnterpriseDatasetRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/datasets/{dataset_id}/status',
      path: {
        'dataset_id': datasetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Groups
   * @returns UserGroupRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseGroupsApiV1EnterpriseGroupsGet(): CancelablePromise<Array<UserGroupRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/groups',
    });
  }
  /**
   * Create Enterprise Group
   * @returns UserGroupRead Successful Response
   * @throws ApiError
   */
  public static createEnterpriseGroupApiV1EnterpriseGroupsPost({
    requestBody,
  }: {
    requestBody: UserGroupCreate,
  }): CancelablePromise<UserGroupRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/groups',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Enterprise Group
   * @returns UserGroupRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseGroupApiV1EnterpriseGroupsGroupIdPut({
    groupId,
    requestBody,
  }: {
    groupId: string,
    requestBody: UserGroupUpdate,
  }): CancelablePromise<UserGroupRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/enterprise/groups/{group_id}',
      path: {
        'group_id': groupId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Enterprise Group Members
   * @returns UserGroupRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseGroupMembersApiV1EnterpriseGroupsGroupIdMembersPut({
    groupId,
    requestBody,
  }: {
    groupId: string,
    requestBody: UserGroupMembershipUpdate,
  }): CancelablePromise<UserGroupRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/enterprise/groups/{group_id}/members',
      path: {
        'group_id': groupId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Llm Providers
   * @returns EnterpriseLLMProviderRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseLlmProvidersApiV1EnterpriseLlmProvidersGet(): CancelablePromise<Array<EnterpriseLLMProviderRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/llm-providers',
    });
  }
  /**
   * Create Enterprise Llm Provider
   * @returns EnterpriseLLMProviderRead Successful Response
   * @throws ApiError
   */
  public static createEnterpriseLlmProviderApiV1EnterpriseLlmProvidersPost({
    requestBody,
  }: {
    requestBody: EnterpriseLLMProviderCreate,
  }): CancelablePromise<EnterpriseLLMProviderRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/llm-providers',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Enterprise Llm Provider
   * @returns EnterpriseLLMProviderRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseLlmProviderApiV1EnterpriseLlmProvidersProviderIdPut({
    providerId,
    requestBody,
  }: {
    providerId: string,
    requestBody: EnterpriseLLMProviderUpdate,
  }): CancelablePromise<EnterpriseLLMProviderRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/enterprise/llm-providers/{provider_id}',
      path: {
        'provider_id': providerId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Make Enterprise Llm Provider Primary
   * @returns EnterpriseLLMProviderRead Successful Response
   * @throws ApiError
   */
  public static makeEnterpriseLlmProviderPrimaryApiV1EnterpriseLlmProvidersProviderIdMakePrimaryPost({
    providerId,
    requestBody,
  }: {
    providerId: string,
    requestBody: EnterpriseLLMProviderPrimaryUpdate,
  }): CancelablePromise<Array<EnterpriseLLMProviderRead>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/llm-providers/{provider_id}/make-primary',
      path: {
        'provider_id': providerId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Test Enterprise Llm Provider
   * @returns EnterpriseLLMProviderRead Successful Response
   * @throws ApiError
   */
  public static testEnterpriseLlmProviderApiV1EnterpriseLlmProvidersProviderIdTestPost({
    providerId,
  }: {
    providerId: string,
  }): CancelablePromise<EnterpriseLLMProviderRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/llm-providers/{provider_id}/test',
      path: {
        'provider_id': providerId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Enterprise Overview
   * @returns EnterpriseOverviewRead Successful Response
   * @throws ApiError
   */
  public static enterpriseOverviewApiV1EnterpriseOverviewGet(): CancelablePromise<EnterpriseOverviewRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/overview',
    });
  }
  /**
   * Enterprise Platform Operations
   * @returns PlatformOperationsRead Successful Response
   * @throws ApiError
   */
  public static enterprisePlatformOperationsApiV1EnterprisePlatformGet(): CancelablePromise<PlatformOperationsRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/platform',
    });
  }
  /**
   * List Enterprise Sessions
   * @returns EnterpriseSessionRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseSessionsApiV1EnterpriseSessionsGet({
    limit = 200,
  }: {
    limit?: number,
  }): CancelablePromise<Array<EnterpriseSessionRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/sessions',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Revoke Enterprise Session
   * @returns EnterpriseSessionRead Successful Response
   * @throws ApiError
   */
  public static revokeEnterpriseSessionApiV1EnterpriseSessionsSessionIdRevokePost({
    sessionId,
    requestBody,
  }: {
    sessionId: string,
    requestBody: EnterpriseSessionRevoke,
  }): CancelablePromise<EnterpriseSessionRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/sessions/{session_id}/revoke',
      path: {
        'session_id': sessionId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Enterprise Users
   * @returns EnterpriseUserRead Successful Response
   * @throws ApiError
   */
  public static listEnterpriseUsersApiV1EnterpriseUsersGet(): CancelablePromise<Array<EnterpriseUserRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/enterprise/users',
    });
  }
  /**
   * Create Enterprise User
   * @returns EnterpriseUserRead Successful Response
   * @throws ApiError
   */
  public static createEnterpriseUserApiV1EnterpriseUsersPost({
    requestBody,
  }: {
    requestBody: EnterpriseUserCreate,
  }): CancelablePromise<EnterpriseUserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/users',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Enterprise User Role
   * @returns EnterpriseUserRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseUserRoleApiV1EnterpriseUsersUserIdRolePost({
    userId,
    requestBody,
  }: {
    userId: string,
    requestBody: EnterpriseUserRoleUpdate,
  }): CancelablePromise<EnterpriseUserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/users/{user_id}/role',
      path: {
        'user_id': userId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Enterprise User Status
   * @returns EnterpriseUserRead Successful Response
   * @throws ApiError
   */
  public static updateEnterpriseUserStatusApiV1EnterpriseUsersUserIdStatusPost({
    userId,
    requestBody,
  }: {
    userId: string,
    requestBody: EnterpriseUserStatusUpdate,
  }): CancelablePromise<EnterpriseUserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/enterprise/users/{user_id}/status',
      path: {
        'user_id': userId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
