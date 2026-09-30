/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { DealLandscapeRead } from './DealLandscapeRead';
import type { DealSearchItemRead } from './DealSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type DealSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<DealSearchItemRead>;
  landscape: DealLandscapeRead;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'announced_at' | 'name' | 'deal_type' | 'status' | 'direction' | 'territory' | 'upfront_amount' | 'total_potential_amount';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
