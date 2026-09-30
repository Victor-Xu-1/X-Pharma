/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BillingDisputeTransition = {
  action: 'investigate' | 'resolve_credit' | 'resolve_no_credit' | 'reject' | 'cancel';
  adjustment_key?: (string | null);
  assigned_to?: (string | null);
  credit_units?: (number | string | null);
  expected_version: number;
  notes: string;
  operation_key: string;
};
