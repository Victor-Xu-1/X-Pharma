/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
import type { ReviewStatus } from './ReviewStatus';
export type EntitySearchQuery = {
  analysis_view?: 'chart' | 'table';
  display_mode?: 'list' | 'landscape';
  entity_type?: (EntityType | null);
  entity_types?: Array<EntityType>;
  include_related?: boolean;
  'q'?: (string | null);
  review_status?: (ReviewStatus | null);
  sort?: Array<string>;
  sort_by?: 'relevance' | 'name' | 'entity_type' | 'updated_at';
  sort_direction?: 'asc' | 'desc';
};
