/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type LegalHoldCreate = {
  matter_reference: string;
  reason: string;
  scope_id?: (string | null);
  scope_type: 'tenant' | 'billing_account' | 'data_export_job' | 'data_source' | 'source_asset';
};
