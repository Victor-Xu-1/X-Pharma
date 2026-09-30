/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DevelopmentPhase } from './DevelopmentPhase';
export type DrugDossierSummaryRead = {
  highest_china_phase?: (DevelopmentPhase | null);
  highest_global_phase?: (DevelopmentPhase | null);
  highest_phase?: (DevelopmentPhase | null);
  indication_count: number;
  latest_status_date?: (string | null);
  modalities: Array<string>;
  organization_count: number;
  program_count: number;
  target_count: number;
};
