/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegulatoryLandscapeBucketRead } from './RegulatoryLandscapeBucketRead';
/**
 * Full-hit-set regulatory statistics for the applied query; missing values are
 * explicit `__missing__` buckets and counts never come from the current page.
 */
export type RegulatoryLandscapeRead = {
  agency?: Array<RegulatoryLandscapeBucketRead>;
  decision_year?: Array<RegulatoryLandscapeBucketRead>;
  event_type?: Array<RegulatoryLandscapeBucketRead>;
  total_events: number;
};
