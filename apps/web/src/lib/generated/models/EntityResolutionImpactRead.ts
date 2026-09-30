/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityReferenceImpactRead } from './EntityReferenceImpactRead';
import type { EntityResolutionCaseRead } from './EntityResolutionCaseRead';
import type { EntityResolutionDecisionRead } from './EntityResolutionDecisionRead';
export type EntityResolutionImpactRead = {
  active_alias_entity_id: (string | null);
  active_canonical_entity_id: (string | null);
  candidate_reference_count: number;
  candidate_trusted_identifier_count: number;
  case: EntityResolutionCaseRead;
  decisions: Array<EntityResolutionDecisionRead>;
  recommendation_reasons: Array<string>;
  recommended_canonical_entity_id: string;
  references: Array<EntityReferenceImpactRead>;
  rollback_available: boolean;
  source_reference_count: number;
  source_trusted_identifier_count: number;
};
