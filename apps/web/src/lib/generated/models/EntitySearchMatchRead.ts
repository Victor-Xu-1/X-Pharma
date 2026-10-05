/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EntitySearchMatchRead = {
  match_relation: 'exact' | 'partial' | 'semantic' | 'related';
  match_type: 'canonical_name' | 'alias' | 'external_id' | 'description' | 'semantic' | 'relationship';
  matched_value?: (string | null);
  namespace?: (string | null);
  predicate?: (string | null);
  source_uri?: (string | null);
  via_entity_id?: (string | null);
};
