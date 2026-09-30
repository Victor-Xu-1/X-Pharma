/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RunState } from './RunState';
export type GovernanceRunRead = {
  completed_at: (string | null);
  created_at: string;
  estimated_cost: (string | null);
  id: string;
  input_sha256: string;
  input_tokens: (number | null);
  model_name: string;
  model_provider: string;
  output_tokens: (number | null);
  policy_current: boolean;
  policy_sha256: string;
  prompt_sha256: string;
  schema_name: string;
  schema_version: string;
  source_asset_id: string;
  source_content_sha256: string;
  source_file_name: string;
  source_logical_path: string;
  source_version_id: string;
  started_at: (string | null);
  status: RunState;
  validation_errors: Array<Record<string, any>>;
};
