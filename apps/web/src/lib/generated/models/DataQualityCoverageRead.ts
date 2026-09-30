/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataQualityCoverageRead = {
  active_asset_count: number;
  asset_count: number;
  authorization_scopes: Array<string>;
  authorization_status: 'valid' | 'expiring' | 'expired' | 'missing_scope' | 'not_yet_valid';
  authorization_valid_until: (string | null);
  conflict_fact_count: number;
  conflict_rate: number;
  consecutive_failures: number;
  data_classification: string;
  dataset_key: string;
  expected_freshness_seconds: number;
  fact_count: number;
  failed_run_count: number;
  failure_sla_age_seconds: (number | null);
  failure_sla_status: 'healthy' | 'at_risk' | 'breached';
  freshness_age_seconds: (number | null);
  freshness_status: 'fresh' | 'stale' | 'never_succeeded';
  ingestion_success_rate: number;
  last_error_present: boolean;
  last_scanned_at: (string | null);
  last_success_at: (string | null);
  measured_at: string;
  name: string;
  owner: string;
  parse_coverage: number;
  parse_missing_count: number;
  parsed_asset_count: number;
  published_fact_count: number;
  published_fact_coverage: number;
  rejected_fact_count: number;
  review_pending_fact_count: number;
  run_count: number;
  source_id: string;
  source_type: string;
  state: string;
  successful_run_count: number;
  window_start: string;
};
