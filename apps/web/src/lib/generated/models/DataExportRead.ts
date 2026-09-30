/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataExportRead = {
  approval_required: boolean;
  approved_at: (string | null);
  approved_by: (string | null);
  artifact_bytes: number;
  artifact_sha256: (string | null);
  completed_at: (string | null);
  dataset: string;
  expires_at: (string | null);
  failure_code: (string | null);
  failure_message: (string | null);
  fields: Array<string>;
  filters: Record<string, any>;
  format: string;
  id: string;
  license_attribution: string;
  license_policy_sha256: string;
  license_policy_version: string;
  manifest_key_id: (string | null);
  manifest_sha256: (string | null);
  manifest_signature: (string | null);
  max_records: number;
  record_count: number;
  requested_at: string;
  started_at: (string | null);
  state: string;
};
