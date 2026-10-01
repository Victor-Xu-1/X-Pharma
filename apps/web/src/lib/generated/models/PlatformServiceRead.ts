/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PlatformServiceRead = {
  detail: string;
  enabled: (boolean | null);
  escalation_policy: string;
  liveness: 'observed' | 'unverified' | 'not_applicable';
  owner: string;
  queue_status: 'healthy' | 'degraded' | 'not_applicable';
  service_id: string;
  status: 'ready' | 'degraded' | 'blocked' | 'external';
};
