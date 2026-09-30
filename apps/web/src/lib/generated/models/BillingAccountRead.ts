/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingAccountRead = {
  account_key: string;
  currency: string;
  display_name: string;
  external_customer_reference_masked: (string | null);
  id: string;
  invoice_count: number;
  mapping_configured: boolean;
  statement_count: number;
  status: 'active' | 'suspended' | 'closed';
  unresolved_statement_count: number;
  updated_at: string;
};
