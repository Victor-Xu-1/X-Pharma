/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityIdentifierRead } from './EntityIdentifierRead';
import type { EntitySearchMatchRead } from './EntitySearchMatchRead';
import type { EntityType } from './EntityType';
import type { ReviewStatus } from './ReviewStatus';
export type EntitySearchItemRead = {
  aliases?: Array<string>;
  attributes: Record<string, any>;
  canonical_entity_id: string;
  created_at: string;
  description: (string | null);
  entity_type: EntityType;
  external_ids: Record<string, string>;
  id: string;
  identity_identifiers?: Array<EntityIdentifierRead>;
  match?: (EntitySearchMatchRead | null);
  name: string;
  review_status: ReviewStatus;
  updated_at: string;
};
