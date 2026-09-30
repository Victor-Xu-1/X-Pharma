/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
  /**
   * Live
   * @returns string Successful Response
   * @throws ApiError
   */
  public static liveHealthLiveGet(): CancelablePromise<Record<string, string>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/health/live',
    });
  }
  /**
   * Ready
   * @returns string Successful Response
   * @throws ApiError
   */
  public static readyHealthReadyGet(): CancelablePromise<Record<string, string>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/health/ready',
    });
  }
}
