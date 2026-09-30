/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { CompetitiveProgramRead } from './CompetitiveProgramRead';
import type { PipelineLandscapeRead } from './PipelineLandscapeRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type PipelineSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets?: Record<string, Record<string, number>>;
  items: Array<CompetitiveProgramRead>;
  landscape: PipelineLandscapeRead;
  limit: number;
  offset: number;
  project_total?: number;
  query_schema_version: string;
  result_grain?: 'program' | 'drug';
  sort?: Array<SortCriterionRead>;
  sort_by: 'status_date' | 'drug_name' | 'target_name' | 'disease_name' | 'organization_name' | 'modality' | 'mechanism_of_action' | 'phase' | 'status_detail' | 'geography' | 'global_phase' | 'china_phase' | 'global_phase_started_at' | 'china_phase_started_at';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings?: Array<string>;
};
