import type { DealSearchFilters } from "../../lib/contracts/deals";

const advancedFields = [
  "directionReferenceJurisdiction",
  "territory",
  "partyCountryRegion",
  "partyOrganizationType",
  "assetModalities",
  "assetProgramTags",
  "developmentPhaseAtTransaction",
  "currentDevelopmentPhase",
  "rightType",
  "rightsTerritory",
  "currency",
  "announcedFrom",
  "announcedTo",
  "terminatedFrom",
  "terminatedTo",
  "sourceUpdatedFrom",
  "sourceUpdatedTo",
  "upfrontAmountMin",
  "upfrontAmountMax",
  "totalPotentialAmountMin",
  "totalPotentialAmountMax",
] as const satisfies readonly (keyof DealSearchFilters)[];

/** Presentation counts only; query execution, validation and persistence have existing owners. */
export function participantFilterCount(filters: DealSearchFilters): number {
  return [
    filters.direction,
    filters.diseaseEntityId,
    filters.partyEntityId || filters.party.trim(),
    filters.partyRole,
  ].filter(Boolean).length;
}

export function advancedDealFilterCount(filters: DealSearchFilters): number {
  return advancedFields.filter((field) => {
    const value = filters[field];
    return Array.isArray(value) ? value.length > 0 : value.trim().length > 0;
  }).length;
}
