/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
export type EvidenceSearchRequest = {
  dataset_keys?: Array<string>;
  entity_types?: Array<EntityType>;
  limit?: number;
  query: string;
};
