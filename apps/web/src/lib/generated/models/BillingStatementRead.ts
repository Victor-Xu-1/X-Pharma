/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingStatementRead = {
  adjustment_count: number;
  adjustment_units: string;
  billing_account_id: string;
  generated_at: string;
  generated_by: string;
  id: string;
  manifest_sha256: string;
  manifest_signature: string;
  net_consumed_units: string;
  payload: Record<string, any>;
  period_end: string;
  period_start: string;
  request_id: string;
  response_bytes: number;
  result_count: number;
  revision: number;
  settlement_count: number;
  settlement_units: string;
  signature_key_id: string;
  statement_key: string;
  subscription_id: string;
};
