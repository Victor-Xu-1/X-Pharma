/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
export type EntityResolutionCaseRead = {
  candidate_entity_id: string;
  candidate_entity_name: string;
  created_at: string;
  entity_type: EntityType;
  id: string;
  proposed_by: string;
  reasons: Array<Record<string, any>>;
  review_notes: (string | null);
  reviewed_at: (string | null);
  reviewed_by_user_id: (string | null);
  risk_tier: 'low' | 'medium' | 'high';
  score: number;
  source_entity_id: string;
  source_entity_name: string;
  status: 'pending' | 'approved' | 'rejected' | 'reverted';
  updated_at: string;
};
