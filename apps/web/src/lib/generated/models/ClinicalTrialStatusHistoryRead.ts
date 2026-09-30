/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ClinicalTrialStatusHistoryRead = {
  effective_at: string;
  effective_at_precision?: ('day' | 'month' | 'year' | null);
  reason?: (string | null);
  source_document_id?: (string | null);
  status: string;
};
