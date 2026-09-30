/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicKnowledgeFactChangeRead } from './PublicKnowledgeFactChangeRead';
import type { PublicKnowledgeSourceChangeRead } from './PublicKnowledgeSourceChangeRead';
export type PublicKnowledgeVersionDiffRead = {
  added_fact_count: number;
  added_facts: Array<PublicKnowledgeFactChangeRead>;
  added_source_count: number;
  added_sources: Array<PublicKnowledgeSourceChangeRead>;
  from_version_number: (number | null);
  removed_fact_count: number;
  removed_facts: Array<PublicKnowledgeFactChangeRead>;
  removed_source_count: number;
  removed_sources: Array<PublicKnowledgeSourceChangeRead>;
  to_version_number: number;
  truncated: boolean;
};
