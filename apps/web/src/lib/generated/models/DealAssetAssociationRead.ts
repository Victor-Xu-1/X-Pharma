/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EntityType } from './EntityType';
export type DealAssetAssociationRead = {
  current_development_phase: (string | null);
  current_phase_as_of: (string | null);
  development_phase_at_transaction: (string | null);
  entity_type: EntityType;
  id: string;
  name: string;
};
