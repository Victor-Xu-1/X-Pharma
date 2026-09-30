/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealLandscapeBucketRead } from './DealLandscapeBucketRead';
export type DealLandscapeRead = {
  asset_modality?: Array<DealLandscapeBucketRead>;
  currency?: Array<DealLandscapeBucketRead>;
  current_phase?: Array<DealLandscapeBucketRead>;
  deal_type?: Array<DealLandscapeBucketRead>;
  direction?: Array<DealLandscapeBucketRead>;
  limit: 5 | 8 | 20 | 50;
  party_country?: Array<DealLandscapeBucketRead>;
  rights_territory?: Array<DealLandscapeBucketRead>;
  status?: Array<DealLandscapeBucketRead>;
  territory?: Array<DealLandscapeBucketRead>;
  total_deals: number;
  transaction_phase?: Array<DealLandscapeBucketRead>;
};
