/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TrialResultDisclosureType } from './TrialResultDisclosureType';
import type { TrialResultEvaluation } from './TrialResultEvaluation';
export type ClinicalTrialResultDisclosureRead = {
  conference_name: (string | null);
  disclosed_at: string;
  disclosure_key: string;
  disclosure_type: TrialResultDisclosureType;
  external_id: (string | null);
  id: string;
  is_key_result: boolean;
  result_evaluation: (TrialResultEvaluation | null);
  source_document_id: (string | null);
  source_locator: (string | null);
  source_quote: (string | null);
  title: string;
  version: number;
};
