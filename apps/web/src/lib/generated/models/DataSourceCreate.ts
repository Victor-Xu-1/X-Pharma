/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemblDataSourceRoutingRule } from './ChemblDataSourceRoutingRule';
import type { ClinicalTrialsGovDataSourceRoutingRule } from './ClinicalTrialsGovDataSourceRoutingRule';
import type { DataSourceType } from './DataSourceType';
import type { PubMedDataSourceRoutingRule } from './PubMedDataSourceRoutingRule';
export type DataSourceCreate = {
  authorization_scopes: Array<string>;
  authorization_valid_from?: string;
  authorization_valid_until?: (string | null);
  credential_ref?: (string | null);
  data_classification?: 'public' | 'internal' | 'confidential' | 'restricted';
  dataset_key: string;
  exclude_globs?: Array<string>;
  expected_freshness_seconds?: number;
  include_globs?: Array<string>;
  max_file_bytes?: number;
  name: string;
  owner: string;
  rate_limit_per_minute?: number;
  root_uri: string;
  routing_rules?: Array<(PubMedDataSourceRoutingRule | ClinicalTrialsGovDataSourceRoutingRule | ChemblDataSourceRoutingRule)>;
  scan_interval_seconds?: number;
  source_type?: DataSourceType;
  stable_seconds?: number;
};
