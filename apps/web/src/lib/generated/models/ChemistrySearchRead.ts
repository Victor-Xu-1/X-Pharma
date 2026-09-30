/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemistrySearchHitRead } from './ChemistrySearchHitRead';
export type ChemistrySearchRead = {
  as_of: string;
  count: number;
  fingerprint_version: (string | null);
  items: Array<ChemistrySearchHitRead>;
  mode: 'exact' | 'substructure' | 'similarity';
  normalized_query: string;
  similarity_threshold: (number | null);
  standardization_version: (string | null);
};
