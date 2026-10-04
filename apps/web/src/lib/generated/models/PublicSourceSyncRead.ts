/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PublicSourceSyncRead = {
  completed_through: (string | null);
  cycle_started_at: string;
  last_completed_at: (string | null);
  pending: boolean;
  phase: 'backfill' | 'incremental' | 'reconcile' | 'full_scan';
  processed_records: number;
  window_end: (string | null);
  window_start: (string | null);
};
