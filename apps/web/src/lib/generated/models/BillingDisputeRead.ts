/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingDisputeRead = {
  assigned_to: (string | null);
  billing_account_id: string;
  billing_account_key: string;
  billing_account_name: string;
  category: 'usage' | 'pricing' | 'duplicate' | 'authorization' | 'service' | 'other';
  created_at: string;
  description: string;
  dispute_key: string;
  disputed_units: string;
  due_at: string;
  external_invoice_id: (string | null);
  id: string;
  invoice_reference_id: (string | null);
  opened_at: string;
  opened_by: string;
  overdue: boolean;
  resolution_adjustment_key: (string | null);
  resolution_code: (string | null);
  resolution_notes: string;
  resolved_at: (string | null);
  resolved_by: (string | null);
  statement_id: string;
  statement_key: string;
  status: 'open' | 'investigating' | 'resolved' | 'rejected' | 'cancelled';
  subject: string;
  subscription_id: string;
  updated_at: string;
  version: number;
};
