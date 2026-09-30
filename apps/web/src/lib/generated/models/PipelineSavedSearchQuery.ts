/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DevelopmentPhase } from './DevelopmentPhase';
import type { TrialResultEvaluation } from './TrialResultEvaluation';
export type PipelineSavedSearchQuery = {
  analysis_dimension?: 'all' | 'global_phase' | 'china_phase' | 'targets' | 'target_combinations' | 'diseases' | 'organizations' | 'modality' | 'geography';
  analysis_limit?: 5 | 8 | 20 | 50 | 100 | 200;
  analysis_stage_scope?: 'overall' | 'global' | 'china';
  analysis_view?: 'chart' | 'table';
  china_phase?: (DevelopmentPhase | null);
  china_phase_started_from?: (string | null);
  china_phase_started_to?: (string | null);
  clinical_result_evaluation?: (TrialResultEvaluation | null);
  commercialization_rights_region?: (string | null);
  deal_currency?: (string | null);
  deal_total_potential_amount_max?: (number | null);
  deal_total_potential_amount_min?: (number | null);
  development_rights_region?: (string | null);
  disease_entity_id?: (string | null);
  display_mode?: 'list' | 'landscape';
  drug_category?: (Array<string> | null);
  drug_entity_id?: (string | null);
  geography?: (string | null);
  global_phase?: (DevelopmentPhase | null);
  global_phase_started_from?: (string | null);
  global_phase_started_to?: (string | null);
  has_clinical_results?: (boolean | null);
  has_deal?: (boolean | null);
  innovation_type?: (Array<string> | null);
  milestone_from?: (string | null);
  milestone_to?: (string | null);
  milestone_type?: (string | null);
  modality?: (Array<string> | null);
  organization_country_region?: (string | null);
  organization_entity_id?: (string | null);
  organization_role?: ('originator' | 'collaborator' | 'licensee' | 'licensor' | 'manufacturer' | 'other' | null);
  organization_type?: (string | null);
  phase?: (DevelopmentPhase | null);
  program_status?: ('active' | 'inactive' | 'unknown' | null);
  program_tag?: (Array<string> | null);
  'q'?: (string | null);
  sort?: Array<string>;
  sort_by?: 'status_date' | 'drug_name' | 'target_name' | 'disease_name' | 'organization_name' | 'modality' | 'mechanism_of_action' | 'phase' | 'status_detail' | 'geography' | 'global_phase' | 'china_phase' | 'global_phase_started_at' | 'china_phase_started_at';
  sort_direction?: 'asc' | 'desc';
  status_date_from?: (string | null);
  status_date_to?: (string | null);
  target_aggregation?: 'all' | 'primary';
  target_combination_key?: (string | null);
  target_entity_id?: (string | null);
  therapeutic_area?: (Array<string> | null);
};
