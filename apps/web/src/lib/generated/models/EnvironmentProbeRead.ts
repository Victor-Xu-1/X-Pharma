/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnvironmentProbeRead = {
  detail: string;
  expected?: (string | null);
  id: string;
  label: string;
  observed?: (string | null);
  scope: 'gateway' | 'host';
  status: 'present' | 'missing' | 'mismatch' | 'blocked' | 'unverified';
};
