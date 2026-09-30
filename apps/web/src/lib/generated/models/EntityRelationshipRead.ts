/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityRead } from './EntityRead';
import type { ReviewStatus } from './ReviewStatus';
export type EntityRelationshipRead = {
  attributes: Record<string, any>;
  direction: 'outgoing' | 'incoming';
  id: string;
  predicate: string;
  related_entity: EntityRead;
  review_status: ReviewStatus;
  valid_from: (string | null);
  valid_to: (string | null);
};
