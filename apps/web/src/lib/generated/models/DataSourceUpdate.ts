/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemblDataSourceRoutingRule } from './ChemblDataSourceRoutingRule';
import type { ClinicalTrialsGovDataSourceRoutingRule } from './ClinicalTrialsGovDataSourceRoutingRule';
import type { PubMedDataSourceRoutingRule } from './PubMedDataSourceRoutingRule';
export type DataSourceUpdate = {
  authorization_scopes?: (Array<string> | null);
  authorization_valid_from?: (string | null);
  authorization_valid_until?: (string | null);
  credential_ref?: (string | null);
  data_classification?: ('public' | 'internal' | 'confidential' | 'restricted' | null);
  dataset_key?: (string | null);
  exclude_globs?: (Array<string> | null);
  expected_freshness_seconds?: (number | null);
  include_globs?: (Array<string> | null);
  max_file_bytes?: (number | null);
  name?: (string | null);
  owner?: (string | null);
  rate_limit_per_minute?: (number | null);
  root_uri?: (string | null);
  routing_rules?: Array<(PubMedDataSourceRoutingRule | ClinicalTrialsGovDataSourceRoutingRule | ChemblDataSourceRoutingRule)>;
  scan_interval_seconds?: (number | null);
  stable_seconds?: (number | null);
};
