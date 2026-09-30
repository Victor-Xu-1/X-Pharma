/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
export type OntologyTermRead = {
  active: boolean;
  content_sha256: string;
  created_at: string;
  definition: (string | null);
  entity_type: EntityType;
  id: string;
  ontology_name: string;
  ontology_version: string;
  parent_term_ids: Array<string>;
  preferred_label: string;
  source_uri: (string | null);
  synonyms: Array<string>;
  term_id: string;
  updated_at: string;
};
