/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EnvironmentInstallResultRead } from './EnvironmentInstallResultRead';
import type { EnvironmentProbeRead } from './EnvironmentProbeRead';
export type HostEnvironmentRead = {
  clean_source: boolean;
  disk_free_bytes: number;
  disk_total_bytes: number;
  generated_at: string;
  latest_install?: (EnvironmentInstallResultRead | null);
  manifest_sha256: string;
  probes: Array<EnvironmentProbeRead>;
  product_version: string;
  revision: string;
  schema_version?: string;
};
