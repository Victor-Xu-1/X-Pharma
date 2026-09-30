/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { EntitySearchItemRead } from './EntitySearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type SearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  engine?: string;
  facets?: Record<string, Record<string, number>>;
  items: Array<EntitySearchItemRead>;
  limit: number;
  offset: number;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'relevance' | 'name' | 'entity_type' | 'updated_at';
  sort_direction: 'asc' | 'desc';
  suggestions?: Array<string>;
  took_ms?: (number | null);
  total: number;
};
