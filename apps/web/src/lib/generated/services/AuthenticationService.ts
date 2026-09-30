/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LoginRequest } from '../models/LoginRequest';
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
}
