/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PlatformEvidenceRead = {
  artifact: string;
  category: 'backup_restore' | 'release_candidate' | 'production_topology';
  detail: string;
  observed_at: (string | null);
  sha256: (string | null);
  status: 'not_configured' | 'missing' | 'passed' | 'failed' | 'invalid';
};
