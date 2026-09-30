/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { NewsEventSearchItemRead } from './NewsEventSearchItemRead';
import type { NewsLandscapeRead } from './NewsLandscapeRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type NewsEventSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<NewsEventSearchItemRead>;
  landscape: NewsLandscapeRead;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'published_at' | 'title' | 'event_type' | 'publisher' | 'venue';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
