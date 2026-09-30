/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PatentLandscapeBucketRead } from './PatentLandscapeBucketRead';
/**
 * Full-hit-set patent statistics computed by the database for the applied query.
 *
 * Buckets always cover the complete authorized result set, never the current page;
 * missing values are reported as explicit `__missing__` buckets instead of being
 * silently dropped.
 */
export type PatentLandscapeRead = {
  legal_status?: Array<PatentLandscapeBucketRead>;
  priority_year?: Array<PatentLandscapeBucketRead>;
  top_applicants?: Array<PatentLandscapeBucketRead>;
  total_families: number;
};
