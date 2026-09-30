/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealPartyRole } from './DealPartyRole';
import type { EntityType } from './EntityType';
export type DealPartyAssociationRead = {
  country_region: (string | null);
  entity_type: EntityType;
  id: string;
  name: string;
  organization_type: (string | null);
  role: DealPartyRole;
};
