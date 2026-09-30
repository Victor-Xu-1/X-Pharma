/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { ClinicalTrialLandscapeRead } from './ClinicalTrialLandscapeRead';
import type { ClinicalTrialSearchItemRead } from './ClinicalTrialSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type ClinicalTrialSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<ClinicalTrialSearchItemRead>;
  landscape: ClinicalTrialLandscapeRead;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'last_update_posted' | 'registry_id' | 'has_results' | 'result_evaluation' | 'overall_status' | 'enrollment' | 'study_type' | 'acronym' | 'initiation_type';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
