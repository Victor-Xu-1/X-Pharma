/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TrialEntityRole } from './TrialEntityRole';
import type { TrialResultEvaluation } from './TrialResultEvaluation';
export type ClinicalTrialSavedSearchQuery = {
  acronym?: (string | null);
  analysis_view?: 'chart' | 'table';
  combination_drug?: (string | null);
  combination_drug_entity_ids?: (Array<string> | null);
  combination_target?: (string | null);
  combination_target_entity_ids?: (Array<string> | null);
  conference?: (string | null);
  disclosed_from?: (string | null);
  disclosed_to?: (string | null);
  display_mode?: 'list' | 'landscape';
  has_key_result?: (boolean | null);
  has_results?: (boolean | null);
  initiation_type?: ('iit' | 'ist' | null);
  investigational_drug?: (string | null);
  investigational_drug_entity_ids?: (Array<string> | null);
  investigational_target?: (string | null);
  investigational_target_entity_ids?: (Array<string> | null);
  linked_drug_category?: (Array<string> | null);
  linked_drug_global_phase?: (string | null);
  linked_drug_innovation_type?: (Array<string> | null);
  linked_drug_modality?: (Array<string> | null);
  linked_drug_organization_country_region?: (string | null);
  linked_drug_program_tag?: (Array<string> | null);
  phase?: (string | null);
  publication_id?: (string | null);
  'q'?: (string | null);
  registry?: (string | null);
  result_evaluation?: (TrialResultEvaluation | null);
  results_posted_from?: (string | null);
  results_posted_to?: (string | null);
  role_entity_id?: (string | null);
  role_entity_ids?: (Array<string> | null);
  role_entity_role?: (TrialEntityRole | null);
  sort?: Array<string>;
  sort_by?: 'last_update_posted' | 'registry_id' | 'has_results' | 'result_evaluation' | 'overall_status' | 'enrollment' | 'study_type' | 'acronym' | 'initiation_type';
  sort_direction?: 'asc' | 'desc';
  status?: (string | null);
  study_type?: (string | null);
  therapy_line?: ('first_line' | 'second_line' | 'third_or_later' | 'prevention' | 'treatment_naive' | 'add_on' | 'adjuvant' | 'neoadjuvant' | 'maintenance' | 'consolidation' | 'induction' | 'conversion' | null);
};
