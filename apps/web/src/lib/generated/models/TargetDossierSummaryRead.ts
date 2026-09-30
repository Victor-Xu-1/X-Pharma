/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DevelopmentPhase } from './DevelopmentPhase';
/**
 * Server-computed target landscape counts over the complete authorized result set.
 *
 * Counts are never derived from the truncated record collections returned alongside
 * them. Free-text source statuses are classified by an explicit versioned vocabulary
 * and anything outside it is reported as unclassified instead of being silently
 * bucketed.
 */
export type TargetDossierSummaryRead = {
  active_patent_count: number;
  approval_event_count: number;
  clinical_trial_count: number;
  highest_phase?: (DevelopmentPhase | null);
  patent_count: number;
  phase_distribution?: Record<string, number>;
  program_count: number;
  recruiting_trial_count: number;
  regulatory_event_count: number;
  status_vocabulary_version: string;
  unclassified_patent_status_count: number;
  unclassified_trial_status_count: number;
};
