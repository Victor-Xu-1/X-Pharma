/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialLandscapeMatrixRowRead } from './ClinicalTrialLandscapeMatrixRowRead';
export type ClinicalTrialLandscapeRead = {
  phase_evaluation?: Array<ClinicalTrialLandscapeMatrixRowRead>;
  publication_year_phase?: Array<ClinicalTrialLandscapeMatrixRowRead>;
  total_trials: number;
};
