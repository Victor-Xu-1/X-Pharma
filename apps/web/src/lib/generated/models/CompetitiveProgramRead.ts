/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ProgramIndicationRead } from './ProgramIndicationRead';
import type { ProgramMilestoneRead } from './ProgramMilestoneRead';
import type { ProgramOrganizationRead } from './ProgramOrganizationRead';
import type { ProgramStatusHistoryRead } from './ProgramStatusHistoryRead';
import type { ProgramTargetRead } from './ProgramTargetRead';
import type { TrialResultEvaluation } from './TrialResultEvaluation';
export type CompetitiveProgramRead = {
  china_phase?: (string | null);
  china_phase_started_at?: (string | null);
  clinical_result_evaluations?: Array<TrialResultEvaluation>;
  clinical_trial_count?: number;
  commercialization_rights_regions?: Array<string>;
  deal_count?: number;
  deal_currencies?: Array<string>;
  development_rights_regions?: Array<string>;
  disease_entity_id: (string | null);
  disease_name: (string | null);
  drug_categories?: Array<string>;
  drug_category?: (string | null);
  drug_entity_id: string;
  drug_name: string;
  geography: (string | null);
  global_phase?: (string | null);
  global_phase_started_at?: (string | null);
  has_clinical_results?: boolean;
  id: string;
  indications?: Array<ProgramIndicationRead>;
  innovation_type?: (string | null);
  innovation_types?: Array<string>;
  mechanism_of_action: (string | null);
  mechanisms_of_action?: Array<string>;
  milestones?: Array<ProgramMilestoneRead>;
  modalities?: Array<string>;
  modality: (string | null);
  organization_entity_id: (string | null);
  organization_name: (string | null);
  organizations?: Array<ProgramOrganizationRead>;
  phase: string;
  program_status?: ('active' | 'inactive' | 'unknown' | null);
  program_status_counts?: Record<string, number>;
  program_tags?: Array<string>;
  project_count?: number;
  source_document_id: (string | null);
  status_date: (string | null);
  status_detail: (string | null);
  status_history?: Array<ProgramStatusHistoryRead>;
  target_combination_key?: (string | null);
  target_entity_id: (string | null);
  target_name: (string | null);
  targets?: Array<ProgramTargetRead>;
  therapeutic_area?: (string | null);
  therapeutic_areas?: Array<string>;
};
