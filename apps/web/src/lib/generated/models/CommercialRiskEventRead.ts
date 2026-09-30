/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CommercialRiskEventRead = {
  actor_type: string;
  case_notes: string;
  case_status: 'open' | 'acknowledged' | 'resolved' | 'dismissed';
  client_id: string;
  client_key: string;
  client_name: string;
  details: Record<string, any>;
  entitlement_key: string;
  existing_unique_records: number;
  id: string;
  occurred_at: string;
  page_depth: number;
  phase: string;
  projected_unique_records: number;
  query_sha256: string;
  reason_code: string;
  request_id: string;
  requested_records: number;
  reviewed_at: (string | null);
  reviewed_by: (string | null);
  subject_id: string;
};
