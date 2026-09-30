/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { RegulatoryEventSearchItemRead } from './RegulatoryEventSearchItemRead';
import type { RegulatoryLandscapeRead } from './RegulatoryLandscapeRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type RegulatoryEventSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<RegulatoryEventSearchItemRead>;
  landscape: RegulatoryLandscapeRead;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'decision_date' | 'title' | 'agency' | 'jurisdiction' | 'event_type' | 'status' | 'subject' | 'source_updated_at';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
