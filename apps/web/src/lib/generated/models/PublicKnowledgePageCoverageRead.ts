/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { KnowledgePredicateCoverageRead } from './KnowledgePredicateCoverageRead';
export type PublicKnowledgePageCoverageRead = {
  cited_fact_count: number;
  fact_count: number;
  linked_entity_count: number;
  predicates: Array<KnowledgePredicateCoverageRead>;
  source_count: number;
  source_snapshot_at: string;
  uncited_fact_count: number;
  version_number: number;
};
