import type { SortCriterion } from "./sorting";

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
