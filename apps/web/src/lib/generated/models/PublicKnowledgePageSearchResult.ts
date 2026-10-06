/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicKnowledgePageSummary } from './PublicKnowledgePageSummary';
export type PublicKnowledgePageSearchResult = {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<PublicKnowledgePageSummary>;
  limit: number;
  offset: number;
  query_schema_version?: string;
  sort_by: 'title' | 'updated_at';
  sort_direction: 'asc' | 'desc';
  total: number;
};
