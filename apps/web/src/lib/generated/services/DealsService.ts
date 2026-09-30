/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DealDirection } from '../models/DealDirection';
import type { DealPartyRole } from '../models/DealPartyRole';
import type { DealRead } from '../models/DealRead';
import type { DealRightType } from '../models/DealRightType';
import type { DealSearchItemRead } from '../models/DealSearchItemRead';
import type { DealSearchResult } from '../models/DealSearchResult';
import type { DealStatus } from '../models/DealStatus';
import type { DevelopmentPhase } from '../models/DevelopmentPhase';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DealsService {
  /**
   * Search Deal Transactions
   * @returns DealSearchResult Successful Response
   * @throws ApiError
   */
  public static searchDealTransactionsApiV1DealTransactionsGet({
    q,
    dealType,
    status,
    direction,
    directionReferenceJurisdiction,
    territory,
    assetEntityId,
    targetEntityId,
    diseaseEntityId,
    assetModality,
    assetProgramTag,
    party,
    partyEntityId,
    partyRole,
    partyCountryRegion,
    partyOrganizationType,
    developmentPhaseAtTransaction,
    currentDevelopmentPhase,
    rightType,
    rightsTerritory,
    currency,
    announcedFrom,
    announcedTo,
    terminatedFrom,
    terminatedTo,
    sourceUpdatedFrom,
    sourceUpdatedTo,
    upfrontAmountMin,
    upfrontAmountMax,
    totalPotentialAmountMin,
    totalPotentialAmountMax,
    limit = 100,
    offset,
    sortBy,
    sortDirection,
    sort,
    analysisTop = 8,
  }: {
    q?: (string | null),
    dealType?: (string | null),
    status?: (DealStatus | null),
    direction?: (DealDirection | null),
    directionReferenceJurisdiction?: (string | null),
    territory?: (string | null),
    assetEntityId?: (string | null),
    targetEntityId?: (string | null),
    diseaseEntityId?: (string | null),
    assetModality?: (Array<string> | null),
    assetProgramTag?: (Array<string> | null),
    party?: (string | null),
    partyEntityId?: (string | null),
    partyRole?: (DealPartyRole | null),
    partyCountryRegion?: (string | null),
    partyOrganizationType?: (string | null),
    developmentPhaseAtTransaction?: (DevelopmentPhase | null),
    currentDevelopmentPhase?: (DevelopmentPhase | null),
    rightType?: (DealRightType | null),
    rightsTerritory?: (string | null),
    currency?: (string | null),
    announcedFrom?: (string | null),
    announcedTo?: (string | null),
    terminatedFrom?: (string | null),
    terminatedTo?: (string | null),
    sourceUpdatedFrom?: (string | null),
    sourceUpdatedTo?: (string | null),
    upfrontAmountMin?: (number | null),
    upfrontAmountMax?: (number | null),
    totalPotentialAmountMin?: (number | null),
    totalPotentialAmountMax?: (number | null),
    limit?: number,
    offset?: number,
    sortBy?: ('announced_at' | 'name' | 'deal_type' | 'status' | 'direction' | 'territory' | 'upfront_amount' | 'total_potential_amount' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
    analysisTop?: number,
  }): CancelablePromise<DealSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/deal-transactions',
      query: {
        'q': q,
        'deal_type': dealType,
        'status': status,
        'direction': direction,
        'direction_reference_jurisdiction': directionReferenceJurisdiction,
        'territory': territory,
        'asset_entity_id': assetEntityId,
        'target_entity_id': targetEntityId,
        'disease_entity_id': diseaseEntityId,
        'asset_modality': assetModality,
        'asset_program_tag': assetProgramTag,
        'party': party,
        'party_entity_id': partyEntityId,
        'party_role': partyRole,
        'party_country_region': partyCountryRegion,
        'party_organization_type': partyOrganizationType,
        'development_phase_at_transaction': developmentPhaseAtTransaction,
        'current_development_phase': currentDevelopmentPhase,
        'right_type': rightType,
        'rights_territory': rightsTerritory,
        'currency': currency,
        'announced_from': announcedFrom,
        'announced_to': announcedTo,
        'terminated_from': terminatedFrom,
        'terminated_to': terminatedTo,
        'source_updated_from': sourceUpdatedFrom,
        'source_updated_to': sourceUpdatedTo,
        'upfront_amount_min': upfrontAmountMin,
        'upfront_amount_max': upfrontAmountMax,
        'total_potential_amount_min': totalPotentialAmountMin,
        'total_potential_amount_max': totalPotentialAmountMax,
        'limit': limit,
        'offset': offset,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
        'analysis_top': analysisTop,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Deal Transaction
   * @returns DealSearchItemRead Successful Response
   * @throws ApiError
   */
  public static getDealTransactionApiV1DealTransactionsDealIdGet({
    dealId,
  }: {
    dealId: string,
  }): CancelablePromise<DealSearchItemRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/deal-transactions/{deal_id}',
      path: {
        'deal_id': dealId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Deals
   * @returns DealRead Successful Response
   * @throws ApiError
   */
  public static searchDealsApiV1DealsGet({
    entityId,
    limit = 100,
  }: {
    entityId?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<DealRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/deals',
      query: {
        'entity_id': entityId,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
