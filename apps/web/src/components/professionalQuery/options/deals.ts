import type { loadDealFacetCatalog } from "../../../lib/contracts/deals";
import {
  dealTypeLabels,
  directionLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../../../lib/dealDisplay";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import { type FacetCatalogState, facetOptions, labeledFacetOptions } from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function dealsOptions(
  draft: ProfessionalSearchDraft,
  dealCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadDealFacetCatalog>>>,
) {
  const dealCatalogState: FacetCatalogState = dealCatalog.isPending
    ? "loading"
    : dealCatalog.isError
      ? "failed"
      : "ready";
  const dealTypeOptions = labeledFacetOptions(dealCatalog.data?.facets?.deal_type, [draft.dealType], dealTypeLabels);
  const dealStatusOptions = labeledFacetOptions(dealCatalog.data?.facets?.status, [draft.dealStatus], statusLabels);
  const dealDirectionOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.direction,
    [draft.dealDirection],
    directionLabels,
  );
  const dealTerritoryOptions = facetOptions(dealCatalog.data?.facets?.territory, [draft.dealTerritory]);
  const dealAssetModalityOptions = facetOptions(dealCatalog.data?.facets?.asset_modality, draft.dealAssetModalities);
  const dealAssetProgramTagOptions = facetOptions(
    dealCatalog.data?.facets?.asset_program_tag,
    draft.dealAssetProgramTags,
  );
  const dealPartyRoleOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.party_role,
    [draft.dealPartyRole],
    partyRoleLabels,
  );
  const dealPartyCountryOptions = facetOptions(dealCatalog.data?.facets?.party_country_region, [
    draft.dealPartyCountryRegion,
  ]);
  const dealPartyOrganizationTypeOptions = facetOptions(dealCatalog.data?.facets?.party_organization_type, [
    draft.dealPartyOrganizationType,
  ]);
  const dealTransactionPhaseOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.development_phase_at_transaction,
    [draft.dealDevelopmentPhaseAtTransaction],
    phaseLabels,
  );
  const dealCurrentPhaseOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.current_development_phase,
    [draft.dealCurrentDevelopmentPhase],
    phaseLabels,
  );
  const dealRightTypeOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.right_type,
    [draft.dealRightType],
    rightTypeLabels,
  );
  const dealRightsTerritoryOptions = facetOptions(dealCatalog.data?.facets?.rights_territory, [
    draft.dealRightsTerritory,
  ]);
  const dealCurrencyOptions = facetOptions(dealCatalog.data?.facets?.currency, [draft.dealCurrency]);
  const dealAdvancedConditionCount =
    draft.dealAssetModalities.length +
    draft.dealAssetProgramTags.length +
    [
      draft.dealDirectionReferenceJurisdiction,
      draft.dealTerritory,
      draft.dealPartyRole,
      draft.dealPartyCountryRegion,
      draft.dealPartyOrganizationType,
      draft.dealDevelopmentPhaseAtTransaction,
      draft.dealCurrentDevelopmentPhase,
      draft.dealRightType,
      draft.dealRightsTerritory,
      draft.dealCurrency,
      draft.dealTerminatedFrom,
      draft.dealTerminatedTo,
      draft.dealSourceUpdatedFrom,
      draft.dealSourceUpdatedTo,
      draft.dealUpfrontAmountMin,
      draft.dealUpfrontAmountMax,
      draft.dealTotalPotentialAmountMin,
      draft.dealTotalPotentialAmountMax,
    ].filter(Boolean).length;

  return {
    dealCatalogState,
    dealTypeOptions,
    dealStatusOptions,
    dealDirectionOptions,
    dealTerritoryOptions,
    dealAssetModalityOptions,
    dealAssetProgramTagOptions,
    dealPartyRoleOptions,
    dealPartyCountryOptions,
    dealPartyOrganizationTypeOptions,
    dealTransactionPhaseOptions,
    dealCurrentPhaseOptions,
    dealRightTypeOptions,
    dealRightsTerritoryOptions,
    dealCurrencyOptions,
    dealAdvancedConditionCount,
  };
}
