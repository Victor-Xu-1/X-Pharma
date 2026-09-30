/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemblDataSourceRoutingRule } from './ChemblDataSourceRoutingRule';
import type { ClinicalTrialsGovDataSourceRoutingRule } from './ClinicalTrialsGovDataSourceRoutingRule';
import type { DataSourceState } from './DataSourceState';
import type { DataSourceType } from './DataSourceType';
import type { PubMedDataSourceRoutingRule } from './PubMedDataSourceRoutingRule';
export type DataSourceRead = {
  authorization_scopes: Array<string>;
  authorization_valid_from: string;
  authorization_valid_until: (string | null);
  config_version: number;
  consecutive_failures: number;
  credential_configured: boolean;
  data_classification: 'public' | 'internal' | 'confidential' | 'restricted';
  dataset_key: string;
  exclude_globs: Array<string>;
  expected_freshness_seconds: number;
  id: string;
  include_globs: Array<string>;
  last_cursor_at: (string | null);
  last_error: (string | null);
  last_scanned_at: (string | null);
  last_success_at: (string | null);
  max_file_bytes: number;
  name: string;
  owner: string;
  rate_limit_per_minute: number;
  root_uri: string;
  routing_rules: Array<(PubMedDataSourceRoutingRule | ClinicalTrialsGovDataSourceRoutingRule | ChemblDataSourceRoutingRule)>;
  scan_interval_seconds: number;
  source_type: DataSourceType;
  stable_seconds: number;
  state: DataSourceState;
  unavailable_since: (string | null);
};
