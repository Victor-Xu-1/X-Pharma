/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyLandscapeBucketRead } from './EpidemiologyLandscapeBucketRead';
/**
 * Full-hit-set epidemiology statistics; missing values are explicit buckets.
 */
export type EpidemiologyLandscapeRead = {
  geography?: Array<EpidemiologyLandscapeBucketRead>;
  measure?: Array<EpidemiologyLandscapeBucketRead>;
  population_scope?: Array<EpidemiologyLandscapeBucketRead>;
  total_observations: number;
};
