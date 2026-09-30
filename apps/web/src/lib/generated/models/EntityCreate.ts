/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
export type EntityCreate = {
  aliases?: Array<string>;
  attributes?: Record<string, any>;
  description?: (string | null);
  entity_type: EntityType;
  external_ids?: Record<string, string>;
  name: string;
};
