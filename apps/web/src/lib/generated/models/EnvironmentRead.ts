/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnvironmentProbeRead } from './EnvironmentProbeRead';
import type { EnvironmentRecipeRead } from './EnvironmentRecipeRead';
import type { HostEnvironmentRead } from './HostEnvironmentRead';
export type EnvironmentRead = {
  environment: string;
  generated_at: string;
  host: (HostEnvironmentRead | null);
  host_detail: string;
  host_status: 'current' | 'stale' | 'missing' | 'invalid' | 'not_configured';
  product_version: string;
  recipes: Array<EnvironmentRecipeRead>;
  runtime: Array<EnvironmentProbeRead>;
};
