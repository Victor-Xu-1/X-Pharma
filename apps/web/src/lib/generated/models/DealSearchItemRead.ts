/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealAssetAssociationRead } from './DealAssetAssociationRead';
import type { DealDirection } from './DealDirection';
import type { DealLinkedEntityRead } from './DealLinkedEntityRead';
import type { DealPartyAssociationRead } from './DealPartyAssociationRead';
import type { DealRightRead } from './DealRightRead';
import type { DealStatus } from './DealStatus';
export type DealSearchItemRead = {
  announced_at: (string | null);
  asset_entities: Array<DealLinkedEntityRead>;
  asset_entity_ids: Array<string>;
  asset_stages: Array<DealAssetAssociationRead>;
  currency: (string | null);
  deal_type: string;
  direction: DealDirection;
  direction_reference_jurisdiction: (string | null);
  entity_id: string;
  id: string;
  name: string;
  parties: Array<Record<string, any>>;
  party_entities: Array<DealLinkedEntityRead>;
  party_roles: Array<DealPartyAssociationRead>;
  rights: Array<DealRightRead>;
  source_document_id: (string | null);
  source_updated_at: (string | null);
  status: DealStatus;
  terminated_at: (string | null);
  terms: Record<string, any>;
  territory: (string | null);
  total_potential_amount: (number | null);
  upfront_amount: (number | null);
};
