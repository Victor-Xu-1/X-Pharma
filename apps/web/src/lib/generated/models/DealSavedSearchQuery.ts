/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealDirection } from './DealDirection';
import type { DealPartyRole } from './DealPartyRole';
import type { DealRightType } from './DealRightType';
import type { DealStatus } from './DealStatus';
import type { DevelopmentPhase } from './DevelopmentPhase';
export type DealSavedSearchQuery = {
  analysis_dimension?: 'all' | 'deal_type' | 'status' | 'direction' | 'territory' | 'currency' | 'asset_modality' | 'transaction_phase' | 'current_phase' | 'party_country' | 'rights_territory';
  analysis_limit?: 5 | 8 | 20 | 50;
  analysis_view?: 'chart' | 'table';
  announced_from?: (string | null);
  announced_to?: (string | null);
  asset_entity_id?: (string | null);
  asset_modality?: (Array<string> | null);
  asset_program_tag?: (Array<string> | null);
  currency?: (string | null);
  current_development_phase?: (DevelopmentPhase | null);
  deal_type?: (string | null);
  development_phase_at_transaction?: (DevelopmentPhase | null);
  direction?: (DealDirection | null);
  direction_reference_jurisdiction?: (string | null);
  disease_entity_id?: (string | null);
  display_mode?: 'list' | 'landscape';
  party?: (string | null);
  party_country_region?: (string | null);
  party_entity_id?: (string | null);
  party_organization_type?: (string | null);
  party_role?: (DealPartyRole | null);
  'q'?: (string | null);
  right_type?: (DealRightType | null);
  rights_territory?: (string | null);
  sort?: Array<string>;
  sort_by?: 'announced_at' | 'name' | 'deal_type' | 'status' | 'direction' | 'territory' | 'upfront_amount' | 'total_potential_amount';
  sort_direction?: 'asc' | 'desc';
  source_updated_from?: (string | null);
  source_updated_to?: (string | null);
  status?: (DealStatus | null);
  target_entity_id?: (string | null);
  terminated_from?: (string | null);
  terminated_to?: (string | null);
  territory?: (string | null);
  total_potential_amount_max?: (number | null);
  total_potential_amount_min?: (number | null);
  upfront_amount_max?: (number | null);
  upfront_amount_min?: (number | null);
};
