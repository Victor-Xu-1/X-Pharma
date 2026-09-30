/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EntitySearchMatchRead = {
  match_relation: 'exact' | 'partial' | 'semantic';
  match_type: 'canonical_name' | 'alias' | 'external_id' | 'description' | 'semantic';
  matched_value?: (string | null);
  namespace?: (string | null);
};
