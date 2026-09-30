/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialOutcomeResultRead } from './ClinicalTrialOutcomeResultRead';
import type { ClinicalTrialStatisticalAnalysisRead } from './ClinicalTrialStatisticalAnalysisRead';
export type ClinicalTrialOutcomeRead = {
  description?: (string | null);
  measure: string;
  outcome_type?: (string | null);
  results?: Array<ClinicalTrialOutcomeResultRead>;
  statistical_analyses?: Array<ClinicalTrialStatisticalAnalysisRead>;
  time_frame?: (string | null);
};
