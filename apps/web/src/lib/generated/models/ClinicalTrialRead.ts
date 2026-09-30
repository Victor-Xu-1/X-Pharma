/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialArmRead } from './ClinicalTrialArmRead';
import type { ClinicalTrialDesignRead } from './ClinicalTrialDesignRead';
import type { ClinicalTrialEligibilityRead } from './ClinicalTrialEligibilityRead';
import type { ClinicalTrialInterventionRead } from './ClinicalTrialInterventionRead';
import type { ClinicalTrialLocationRead } from './ClinicalTrialLocationRead';
import type { ClinicalTrialOutcomeRead } from './ClinicalTrialOutcomeRead';
import type { ClinicalTrialSponsorRead } from './ClinicalTrialSponsorRead';
import type { ClinicalTrialStatusHistoryRead } from './ClinicalTrialStatusHistoryRead';
import type { TrialResultEvaluation } from './TrialResultEvaluation';
export type ClinicalTrialRead = {
  acronym: (string | null);
  arms: Array<ClinicalTrialArmRead>;
  completion_date: (string | null);
  completion_date_precision: ('day' | 'month' | 'year' | null);
  conditions: Array<string>;
  eligibility: ClinicalTrialEligibilityRead;
  enrollment: (number | null);
  entity_id: string;
  has_results: boolean;
  id: string;
  initiation_type: ('iit' | 'ist' | null);
  interventions: Array<ClinicalTrialInterventionRead>;
  last_update_posted: (string | null);
  locations: Array<ClinicalTrialLocationRead>;
  official_title: string;
  outcomes: Array<ClinicalTrialOutcomeRead>;
  overall_status: (string | null);
  phases: Array<string>;
  registry_id: string;
  registry_name: string;
  result_evaluation: (TrialResultEvaluation | null);
  results_first_posted: (string | null);
  source_document_id: (string | null);
  sponsors: Array<ClinicalTrialSponsorRead>;
  start_date: (string | null);
  start_date_precision: ('day' | 'month' | 'year' | null);
  status_history: Array<ClinicalTrialStatusHistoryRead>;
  study_design: ClinicalTrialDesignRead;
  study_type: (string | null);
  therapy_lines: Array<'first_line' | 'second_line' | 'third_or_later' | 'prevention' | 'treatment_naive' | 'add_on' | 'adjuvant' | 'neoadjuvant' | 'maintenance' | 'consolidation' | 'induction' | 'conversion'>;
};
