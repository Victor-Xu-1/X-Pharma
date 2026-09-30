/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityRead } from './EntityRead';
export type TargetProfileResponse = {
  activity_count: number;
  as_of: string;
  entity: EntityRead;
  function_summary?: (string | null);
  gene_symbol?: (string | null);
  organism?: (string | null);
  profile_id?: (string | null);
  program_count: number;
  sequence?: (string | null);
  source_document_id?: (string | null);
  target_class?: (string | null);
  target_evidence_count?: number;
  uniprot_accession?: (string | null);
};
