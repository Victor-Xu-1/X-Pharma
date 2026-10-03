/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InvitationAcceptance } from '../models/InvitationAcceptance';
import type { InvitationCreate } from '../models/InvitationCreate';
import type { InvitationIssued } from '../models/InvitationIssued';
import type { InvitationRead } from '../models/InvitationRead';
import type { LoginRequest } from '../models/LoginRequest';
import type { OidcInvitationStart } from '../models/OidcInvitationStart';
import type { OrganizationJoin } from '../models/OrganizationJoin';
import type { OrganizationRead } from '../models/OrganizationRead';
import type { OrganizationSwitch } from '../models/OrganizationSwitch';
import type { RegistrationPolicy } from '../models/RegistrationPolicy';
import type { RegistrationRequest } from '../models/RegistrationRequest';
import type { UserPasswordChange } from '../models/UserPasswordChange';
import type { UserProfileUpdate } from '../models/UserProfileUpdate';
import type { UserRead } from '../models/UserRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuthenticationService {
  /**
   * Authentication Config
   * @returns string Successful Response
   * @throws ApiError
   */
  public static authenticationConfigApiV1AuthConfigGet(): CancelablePromise<Record<string, string>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/config',
    });
  }
  /**
   * Accept Invitation With Credentials
   * Permit a locally verified identity with no active org to accept an invitation.
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static acceptInvitationWithCredentialsApiV1AuthInvitationsAcceptPost({
    requestBody,
  }: {
    requestBody: InvitationAcceptance,
  }): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/invitations/accept',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Login
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static loginApiV1AuthLoginPost({
    requestBody,
  }: {
    requestBody: LoginRequest,
  }): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/login',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Logout
   * @returns void
   * @throws ApiError
   */
  public static logoutApiV1AuthLogoutPost(): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/logout',
    });
  }
  /**
   * Current User
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static currentUserApiV1AuthMeGet(): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/me',
    });
  }
  /**
   * Update Current User
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static updateCurrentUserApiV1AuthMePatch({
    requestBody,
  }: {
    requestBody: UserProfileUpdate,
  }): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'PATCH',
      url: '/api/v1/auth/me',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Change Current User Password
   * @returns void
   * @throws ApiError
   */
  public static changeCurrentUserPasswordApiV1AuthMePasswordPost({
    requestBody,
  }: {
    requestBody: UserPasswordChange,
  }): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/me/password',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Oidc Callback
   * @returns any Successful Response
   * @throws ApiError
   */
  public static oidcCallbackApiV1AuthOidcCallbackGet({
    code,
    state,
  }: {
    code: string,
    state: string,
  }): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/oidc/callback',
      query: {
        'code': code,
        'state': state,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Start Oidc Invitation
   * @returns OidcInvitationStart Successful Response
   * @throws ApiError
   */
  public static startOidcInvitationApiV1AuthOidcInvitationPost({
    requestBody,
  }: {
    requestBody: OrganizationJoin,
  }): CancelablePromise<OidcInvitationStart> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/oidc/invitation',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Oidc Login
   * @returns any Successful Response
   * @throws ApiError
   */
  public static oidcLoginApiV1AuthOidcLoginGet(): CancelablePromise<any> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/oidc/login',
    });
  }
  /**
   * List Organizations
   * @returns OrganizationRead Successful Response
   * @throws ApiError
   */
  public static listOrganizationsApiV1AuthOrganizationsGet(): CancelablePromise<Array<OrganizationRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/organizations',
    });
  }
  /**
   * Join Organization
   * @returns OrganizationRead Successful Response
   * @throws ApiError
   */
  public static joinOrganizationApiV1AuthOrganizationsJoinPost({
    requestBody,
  }: {
    requestBody: OrganizationJoin,
  }): CancelablePromise<OrganizationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/organizations/join',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Switch Organization
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static switchOrganizationApiV1AuthOrganizationsSwitchPost({
    requestBody,
  }: {
    requestBody: OrganizationSwitch,
  }): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/organizations/switch',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Register Account
   * @returns UserRead Successful Response
   * @throws ApiError
   */
  public static registerAccountApiV1AuthRegisterPost({
    requestBody,
  }: {
    requestBody: RegistrationRequest,
  }): CancelablePromise<UserRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/auth/register',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Registration Policy
   * @returns RegistrationPolicy Successful Response
   * @throws ApiError
   */
  public static registrationPolicyApiV1AuthRegistrationPolicyGet(): CancelablePromise<RegistrationPolicy> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/auth/registration-policy',
    });
  }
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
}
