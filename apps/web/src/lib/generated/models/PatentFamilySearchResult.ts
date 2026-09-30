/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { PatentFamilySearchItemRead } from './PatentFamilySearchItemRead';
import type { PatentLandscapeRead } from './PatentLandscapeRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type PatentFamilySearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<PatentFamilySearchItemRead>;
  landscape: PatentLandscapeRead;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'priority_date' | 'family_identifier' | 'legal_status' | 'expiration_date';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
