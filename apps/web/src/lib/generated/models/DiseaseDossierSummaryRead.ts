/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DevelopmentPhase } from './DevelopmentPhase';
export type DiseaseDossierSummaryRead = {
  clinical_trial_count: number;
  drug_count: number;
  epidemiology_observation_count: number;
  geographies?: Array<string>;
  highest_phase?: (DevelopmentPhase | null);
  latest_activity_at?: (string | null);
  measures?: Array<string>;
  modalities?: Array<string>;
  organization_count: number;
  patent_count: number;
  patient_population_count: number;
  phase_distribution?: Record<string, number>;
  program_count: number;
  target_count: number;
};
