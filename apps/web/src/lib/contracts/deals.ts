import { contractRequest } from "../contract";
import type { DealSavedSearchQuery, DealSearchItemRead, DealSearchResult } from "../generated";
import { DealsService } from "../generated";
import { developmentPhases } from "../phasePresentation";
import {
  assertValidDealSearchFilters,
  dealDirections,
  dealStatuses,
  partyRoles,
  rightTypes,
} from "./dealFilterValidation";
import { type SavedSearchCreationOutcome, saveAndSubscribeSearch } from "./savedSearchCreation";
import { effectiveSort, type SortCriterion } from "./sorting";

export const dealSortFields = [
  "announced_at",
  "name",
  "deal_type",
  "status",
  "direction",
  "territory",
  "upfront_amount",
  "total_potential_amount",
] as const;
export type DealSortField = (typeof dealSortFields)[number];

export const dealAnalysisDimensions = [
  "all",
  "deal_type",
  "status",
  "direction",
  "territory",
  "currency",
  "asset_modality",
  "transaction_phase",
  "current_phase",
  "party_country",
  "rights_territory",
] as const;
export type DealAnalysisDimension = (typeof dealAnalysisDimensions)[number];
export type DealAnalysisView = "chart" | "table";
export type DealAnalysisLimit = 5 | 8 | 20 | 50;

export interface DealAnalysisOptions {
  dimension: DealAnalysisDimension;
  view: DealAnalysisView;
  limit: DealAnalysisLimit;
}

export interface DealSearchFilters {
  query: string;
  dealType: string;
  status: string;
  direction: string;
  directionReferenceJurisdiction: string;
  territory: string;
  assetEntityId: string;
  targetEntityId: string;
  diseaseEntityId: string;
  assetModalities: string[];
  assetProgramTags: string[];
  party: string;
  partyEntityId: string;
  partyRole: string;
  partyCountryRegion: string;
  partyOrganizationType: string;
  developmentPhaseAtTransaction: string;
  currentDevelopmentPhase: string;
  rightType: string;
  rightsTerritory: string;
  currency: string;
  announcedFrom: string;
  announcedTo: string;
  terminatedFrom: string;
  terminatedTo: string;
  sourceUpdatedFrom: string;
  sourceUpdatedTo: string;
  upfrontAmountMin: string;
  upfrontAmountMax: string;
  totalPotentialAmountMin: string;
  totalPotentialAmountMax: string;
  sortBy: DealSortField;
  sortDirection: "asc" | "desc";
  sort?: SortCriterion<DealSortField>[];
}

export const emptyDealSearchFilters: DealSearchFilters = {
  query: "",
  dealType: "",
  status: "",
  direction: "",
  directionReferenceJurisdiction: "",
  territory: "",
  assetEntityId: "",
  targetEntityId: "",
  diseaseEntityId: "",
  assetModalities: [],
  assetProgramTags: [],
  party: "",
  partyEntityId: "",
  partyRole: "",
  partyCountryRegion: "",
  partyOrganizationType: "",
  developmentPhaseAtTransaction: "",
  currentDevelopmentPhase: "",
  rightType: "",
  rightsTerritory: "",
  currency: "",
  announcedFrom: "",
  announcedTo: "",
  terminatedFrom: "",
  terminatedTo: "",
  sourceUpdatedFrom: "",
  sourceUpdatedTo: "",
  upfrontAmountMin: "",
  upfrontAmountMax: "",
  totalPotentialAmountMin: "",
  totalPotentialAmountMax: "",
  sortBy: "announced_at",
  sortDirection: "desc",
  sort: [{ field: "announced_at", direction: "desc" }],
};

export interface DealFacetCatalog {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  warnings: string[];
}

export { validateDealSearchFilters } from "./dealFilterValidation";

function enumValue<T extends string>(value: string, values: ReadonlySet<T>): T | undefined {
  return values.has(value as T) ? (value as T) : undefined;
}

function amount(value: string): number | undefined {
  if (!value.trim()) return undefined;
  return Number(value);
}

function savedDealQuery(
  filters: DealSearchFilters,
  displayMode: "list" | "landscape" = "list",
  analysis: DealAnalysisOptions = { dimension: "all", view: "chart", limit: 8 },
): DealSavedSearchQuery {
  return {
    q: filters.query.trim() || undefined,
    deal_type: filters.dealType || undefined,
    status: enumValue(filters.status, dealStatuses),
    direction: enumValue(filters.direction, dealDirections),
    direction_reference_jurisdiction: filters.directionReferenceJurisdiction.trim() || undefined,
    territory: filters.territory || undefined,
    asset_entity_id: filters.assetEntityId || undefined,
    target_entity_id: filters.targetEntityId || undefined,
    disease_entity_id: filters.diseaseEntityId || undefined,
    asset_modality: filters.assetModalities.length ? filters.assetModalities : undefined,
    asset_program_tag: filters.assetProgramTags.length ? filters.assetProgramTags : undefined,
    party: filters.partyEntityId ? undefined : filters.party.trim() || undefined,
    party_entity_id: filters.partyEntityId || undefined,
    party_role: enumValue(filters.partyRole, partyRoles),
    party_country_region: filters.partyCountryRegion || undefined,
    party_organization_type: filters.partyOrganizationType || undefined,
    development_phase_at_transaction: enumValue(filters.developmentPhaseAtTransaction, developmentPhases),
    current_development_phase: enumValue(filters.currentDevelopmentPhase, developmentPhases),
    right_type: enumValue(filters.rightType, rightTypes),
    rights_territory: filters.rightsTerritory || undefined,
    currency: filters.currency || undefined,
    announced_from: filters.announcedFrom || undefined,
    announced_to: filters.announcedTo || undefined,
    terminated_from: filters.terminatedFrom || undefined,
    terminated_to: filters.terminatedTo || undefined,
    source_updated_from: filters.sourceUpdatedFrom || undefined,
    source_updated_to: filters.sourceUpdatedTo || undefined,
    upfront_amount_min: amount(filters.upfrontAmountMin),
    upfront_amount_max: amount(filters.upfrontAmountMax),
    total_potential_amount_min: amount(filters.totalPotentialAmountMin),
    total_potential_amount_max: amount(filters.totalPotentialAmountMax),
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
    sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: displayMode,
    analysis_dimension: analysis.dimension,
    analysis_view: analysis.view,
    analysis_limit: analysis.limit,
  };
}

export function hasDealSearchFilter(filters: DealSearchFilters): boolean {
  return Object.entries(filters).some(
    ([key, value]) =>
      !["sortBy", "sortDirection", "sort"].includes(key) &&
      (Array.isArray(value) ? value.length > 0 : typeof value === "string" && value.trim().length > 0),
  );
}

export async function saveDealSearch({
  name,
  filters,
  displayMode,
  analysis,
  shared,
  monitor,
}: {
  name: string;
  filters: DealSearchFilters;
  displayMode: "list" | "landscape";
  analysis: DealAnalysisOptions;
  shared: boolean;
  monitor: boolean;
}): Promise<SavedSearchCreationOutcome> {
  assertValidDealSearchFilters(filters);
  return saveAndSubscribeSearch(
    {
      name: name.trim(),
      query_type: "deal_search",
      query: savedDealQuery(filters, displayMode, analysis),
      visibility: shared ? "tenant" : "private",
    },
    monitor,
  );
}

export const dealKeys = {
  search: (filters: DealSearchFilters, offset: number, analysisLimit: DealAnalysisLimit) =>
    ["intelligence", "deals", { ...filters, offset, analysisLimit }] as const,
  detail: (dealId: string) => ["intelligence", "deals", "detail", dealId] as const,
  facetCatalog: () => ["intelligence", "deals", "facet-catalog"] as const,
};

export async function loadDealFacetCatalog(signal?: AbortSignal): Promise<DealFacetCatalog> {
  const result = await contractRequest(
    DealsService.searchDealTransactionsApiV1DealTransactionsGet({
      limit: 1,
      offset: 0,
      sort: ["announced_at:desc"],
      analysisTop: 5,
    }),
    signal,
  );
  return { as_of: result.as_of, facets: result.facets, warnings: result.warnings };
}

export async function searchDeals(
  filters: DealSearchFilters,
  offset: number,
  analysisLimit: DealAnalysisLimit,
  signal?: AbortSignal,
): Promise<DealSearchResult> {
  assertValidDealSearchFilters(filters);
  return contractRequest(
    DealsService.searchDealTransactionsApiV1DealTransactionsGet({
      q: filters.query.trim() || undefined,
      dealType: filters.dealType || undefined,
      status: enumValue(filters.status, dealStatuses),
      direction: enumValue(filters.direction, dealDirections),
      directionReferenceJurisdiction: filters.directionReferenceJurisdiction.trim() || undefined,
      territory: filters.territory || undefined,
      assetEntityId: filters.assetEntityId || undefined,
      targetEntityId: filters.targetEntityId || undefined,
      diseaseEntityId: filters.diseaseEntityId || undefined,
      assetModality: filters.assetModalities.length ? filters.assetModalities : undefined,
      assetProgramTag: filters.assetProgramTags.length ? filters.assetProgramTags : undefined,
      party: filters.partyEntityId ? undefined : filters.party.trim() || undefined,
      partyEntityId: filters.partyEntityId || undefined,
      partyRole: enumValue(filters.partyRole, partyRoles),
      partyCountryRegion: filters.partyCountryRegion || undefined,
      partyOrganizationType: filters.partyOrganizationType || undefined,
      developmentPhaseAtTransaction: enumValue(filters.developmentPhaseAtTransaction, developmentPhases),
      currentDevelopmentPhase: enumValue(filters.currentDevelopmentPhase, developmentPhases),
      rightType: enumValue(filters.rightType, rightTypes),
      rightsTerritory: filters.rightsTerritory || undefined,
      currency: filters.currency || undefined,
      announcedFrom: filters.announcedFrom ? `${filters.announcedFrom}T00:00:00.000Z` : undefined,
      announcedTo: filters.announcedTo ? `${filters.announcedTo}T23:59:59.999Z` : undefined,
      terminatedFrom: filters.terminatedFrom ? `${filters.terminatedFrom}T00:00:00.000Z` : undefined,
      terminatedTo: filters.terminatedTo ? `${filters.terminatedTo}T23:59:59.999Z` : undefined,
      sourceUpdatedFrom: filters.sourceUpdatedFrom ? `${filters.sourceUpdatedFrom}T00:00:00.000Z` : undefined,
      sourceUpdatedTo: filters.sourceUpdatedTo ? `${filters.sourceUpdatedTo}T23:59:59.999Z` : undefined,
      upfrontAmountMin: amount(filters.upfrontAmountMin),
      upfrontAmountMax: amount(filters.upfrontAmountMax),
      totalPotentialAmountMin: amount(filters.totalPotentialAmountMin),
      totalPotentialAmountMax: amount(filters.totalPotentialAmountMax),
      sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      analysisTop: analysisLimit,
      limit: 100,
      offset,
    }),
    signal,
  );
}

export async function loadDealDetail(dealId: string, signal?: AbortSignal): Promise<DealSearchItemRead> {
  return contractRequest(DealsService.getDealTransactionApiV1DealTransactionsDealIdGet({ dealId }), signal);
}
