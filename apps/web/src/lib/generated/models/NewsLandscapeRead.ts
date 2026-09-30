/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewsLandscapeBucketRead } from './NewsLandscapeBucketRead';
/**
 * Full-hit-set news statistics; missing values are explicit buckets.
 */
export type NewsLandscapeRead = {
  event_type?: Array<NewsLandscapeBucketRead>;
  published_year?: Array<NewsLandscapeBucketRead>;
  total_events: number;
  venue?: Array<NewsLandscapeBucketRead>;
};
