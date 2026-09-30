/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityIdentifierRead } from './EntityIdentifierRead';
import type { EntityType } from './EntityType';
import type { ReviewStatus } from './ReviewStatus';
export type EntityRead = {
  attributes: Record<string, any>;
  canonical_entity_id: string;
  created_at: string;
  description: (string | null);
  entity_type: EntityType;
  external_ids: Record<string, string>;
  id: string;
  identity_identifiers?: Array<EntityIdentifierRead>;
  name: string;
  review_status: ReviewStatus;
  updated_at: string;
};
