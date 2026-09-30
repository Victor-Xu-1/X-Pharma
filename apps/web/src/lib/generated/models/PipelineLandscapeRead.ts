/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PipelineLandscapeBucketRead } from './PipelineLandscapeBucketRead';
export type PipelineLandscapeRead = {
  china_phase?: Array<PipelineLandscapeBucketRead>;
  diseases?: Array<PipelineLandscapeBucketRead>;
  distinct_diseases: number;
  distinct_drugs: number;
  distinct_organizations: number;
  distinct_targets: number;
  geography?: Array<PipelineLandscapeBucketRead>;
  global_phase?: Array<PipelineLandscapeBucketRead>;
  limit: number;
  modality?: Array<PipelineLandscapeBucketRead>;
  organizations?: Array<PipelineLandscapeBucketRead>;
  overall_phase?: Array<PipelineLandscapeBucketRead>;
  stage_scope: 'overall' | 'global' | 'china';
  target_aggregation: 'all' | 'primary';
  target_combinations?: Array<PipelineLandscapeBucketRead>;
  targets?: Array<PipelineLandscapeBucketRead>;
  total_programs: number;
};
