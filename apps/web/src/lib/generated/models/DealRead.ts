/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealDirection } from './DealDirection';
import type { DealStatus } from './DealStatus';
export type DealRead = {
  announced_at: (string | null);
  asset_entity_ids: Array<string>;
  currency: (string | null);
  deal_type: string;
  direction: DealDirection;
  direction_reference_jurisdiction: (string | null);
  entity_id: string;
  id: string;
  parties: Array<Record<string, any>>;
  source_document_id: (string | null);
  source_updated_at: (string | null);
  status: DealStatus;
  terminated_at: (string | null);
  terms: Record<string, any>;
  territory: (string | null);
  total_potential_amount: (number | null);
  upfront_amount: (number | null);
};
