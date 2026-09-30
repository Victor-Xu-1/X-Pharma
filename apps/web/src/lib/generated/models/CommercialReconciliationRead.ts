/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CommercialReconciliationRead = {
  completed_at: string;
  id: string;
  issue_count: number;
  issues: Array<Record<string, any>>;
  ledger_consumed_units: string;
  ledger_granted_units: string;
  ledger_reserved_units: string;
  request_id: string;
  requested_by: string;
  run_key: string;
  snapshot_consumed_units: string;
  snapshot_granted_units: string;
  snapshot_reserved_units: string;
  source_consumed_units: string;
  source_granted_units: string;
  source_reserved_units: string;
  started_at: string;
  status: string;
  subscription_id: string;
};
