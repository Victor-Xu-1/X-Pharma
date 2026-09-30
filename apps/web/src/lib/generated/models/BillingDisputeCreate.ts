/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingDisputeCreate = {
  category: 'usage' | 'pricing' | 'duplicate' | 'authorization' | 'service' | 'other';
  description: string;
  dispute_key: string;
  disputed_units: (number | string);
  invoice_reference_id?: (string | null);
  statement_id: string;
  subject: string;
};
