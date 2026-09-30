/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingDeliveryRead = {
  attempts: number;
  available_at: string;
  billing_account_id: string;
  billing_account_key: string;
  billing_account_name: string;
  created_at: string;
  delivery_id: (string | null);
  event_id: string;
  external_invoice_id: (string | null);
  invoice_provider: (string | null);
  invoice_status: (string | null);
  last_error: (string | null);
  lease_expires_at: (string | null);
  processed_at: (string | null);
  state: 'pending' | 'processing' | 'retry' | 'succeeded' | 'dead';
  statement_id: string;
  statement_key: string;
};
