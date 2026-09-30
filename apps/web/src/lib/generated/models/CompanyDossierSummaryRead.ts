/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DevelopmentPhase } from './DevelopmentPhase';
export type CompanyDossierSummaryRead = {
  deal_count: number;
  drug_count: number;
  highest_phase?: (DevelopmentPhase | null);
  indication_count: number;
  latest_activity_at?: (string | null);
  modalities?: Array<string>;
  phase_distribution?: Record<string, number>;
  program_count: number;
  target_count: number;
  timeline_event_count: number;
};
