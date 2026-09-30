/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemistrySearchHitRead } from './ChemistrySearchHitRead';
export type AgentChemistrySearchRead = {
  as_of: string;
  count: number;
  fingerprint_version: (string | null);
  items: Array<ChemistrySearchHitRead>;
  limit: number;
  mode: 'exact' | 'substructure' | 'similarity';
  next_cursor: (string | null);
  normalized_query: string;
  page_depth: number;
  similarity_threshold: (number | null);
  standardization_version: (string | null);
};
