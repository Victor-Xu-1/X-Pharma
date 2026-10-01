import { lazy } from "react";
import type {
  DealAnalysisDimension,
  DealAnalysisLimit,
  DealAnalysisView,
  DealSearchFilters,
} from "../../lib/contracts/deals";
import type { ResearchRouteContext } from "./routeContext";

const DealsView = lazy(() => import("../../views/DealsView").then((module) => ({ default: module.DealsView })));

export function DealsRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <DealsView
      displayMode={location.dealDisplayMode ?? "list"}
      analysisDimension={(location.dealAnalysisDimension ?? "all") as DealAnalysisDimension}
      analysisView={(location.dealAnalysisView ?? "chart") as DealAnalysisView}
      analysisLimit={(location.dealAnalysisLimit ?? 8) as DealAnalysisLimit}
      initialFilters={{
        query: location.query,
        dealType: location.dealType ?? "",
        status: location.dealStatus ?? "",
        direction: location.dealDirection ?? "",
        directionReferenceJurisdiction: location.dealDirectionReferenceJurisdiction ?? "",
        territory: location.dealTerritory ?? "",
        assetEntityId: location.dealAssetEntityId ?? "",
        targetEntityId: location.dealTargetEntityId ?? "",
        diseaseEntityId: location.dealDiseaseEntityId ?? "",
        assetModalities: location.dealAssetModalities ?? [],
        assetProgramTags: location.dealAssetProgramTags ?? [],
        party: location.dealParty ?? "",
        partyEntityId: location.dealPartyEntityId ?? "",
        partyRole: location.dealPartyRole ?? "",
        partyCountryRegion: location.dealPartyCountryRegion ?? "",
        partyOrganizationType: location.dealPartyOrganizationType ?? "",
        developmentPhaseAtTransaction: location.dealDevelopmentPhaseAtTransaction ?? "",
        currentDevelopmentPhase: location.dealCurrentDevelopmentPhase ?? "",
        rightType: location.dealRightType ?? "",
        rightsTerritory: location.dealRightsTerritory ?? "",
        currency: location.dealCurrency ?? "",
        announcedFrom: location.dealAnnouncedFrom ?? "",
        announcedTo: location.dealAnnouncedTo ?? "",
        terminatedFrom: location.dealTerminatedFrom ?? "",
        terminatedTo: location.dealTerminatedTo ?? "",
        sourceUpdatedFrom: location.dealSourceUpdatedFrom ?? "",
        sourceUpdatedTo: location.dealSourceUpdatedTo ?? "",
        upfrontAmountMin: location.dealUpfrontAmountMin ?? "",
        upfrontAmountMax: location.dealUpfrontAmountMax ?? "",
        totalPotentialAmountMin: location.dealTotalPotentialAmountMin ?? "",
        totalPotentialAmountMax: location.dealTotalPotentialAmountMax ?? "",
        sortBy: (location.dealSortBy ?? "announced_at") as DealSearchFilters["sortBy"],
        sortDirection: location.dealSortDirection ?? "desc",
        sort: location.dealSort as DealSearchFilters["sort"],
      }}
      initialOffset={location.offset ?? 0}
      selectedDealId={location.dealId ?? null}
      activeSection={location.dealSection ?? "overview"}
      onSearchChange={(filters, offset) =>
        navigate({
          workbench: "research",
          view: "deals",
          query: filters.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          dealType: filters.dealType,
          dealStatus: filters.status,
          dealDirection: filters.direction,
          dealDirectionReferenceJurisdiction: filters.directionReferenceJurisdiction,
          dealTerritory: filters.territory,
          dealAssetEntityId: filters.assetEntityId,
          dealTargetEntityId: filters.targetEntityId,
          dealDiseaseEntityId: filters.diseaseEntityId,
          dealAssetModalities: filters.assetModalities,
          dealAssetProgramTags: filters.assetProgramTags,
          dealParty: filters.party,
          dealPartyEntityId: filters.partyEntityId,
          dealPartyRole: filters.partyRole,
          dealPartyCountryRegion: filters.partyCountryRegion,
          dealPartyOrganizationType: filters.partyOrganizationType,
          dealDevelopmentPhaseAtTransaction: filters.developmentPhaseAtTransaction,
          dealCurrentDevelopmentPhase: filters.currentDevelopmentPhase,
          dealRightType: filters.rightType,
          dealRightsTerritory: filters.rightsTerritory,
          dealCurrency: filters.currency,
          dealAnnouncedFrom: filters.announcedFrom,
          dealAnnouncedTo: filters.announcedTo,
          dealTerminatedFrom: filters.terminatedFrom,
          dealTerminatedTo: filters.terminatedTo,
          dealSourceUpdatedFrom: filters.sourceUpdatedFrom,
          dealSourceUpdatedTo: filters.sourceUpdatedTo,
          dealUpfrontAmountMin: filters.upfrontAmountMin,
          dealUpfrontAmountMax: filters.upfrontAmountMax,
          dealTotalPotentialAmountMin: filters.totalPotentialAmountMin,
          dealTotalPotentialAmountMax: filters.totalPotentialAmountMax,
          dealSort: filters.sort,
          dealSortBy: filters.sortBy,
          dealSortDirection: filters.sortDirection,
          dealDisplayMode: location.dealDisplayMode ?? "list",
          dealAnalysisDimension: location.dealAnalysisDimension ?? "all",
          dealAnalysisView: location.dealAnalysisView ?? "chart",
          dealAnalysisLimit: location.dealAnalysisLimit ?? 8,
          dealId: null,
          invalidDealId: false,
          offset,
        })
      }
      onDisplayModeChange={(dealDisplayMode) => navigate({ ...location, dealDisplayMode, offset: 0 })}
      onAnalysisChange={({ dimension, view, limit }) =>
        navigate({
          ...location,
          dealDisplayMode: "landscape",
          dealAnalysisDimension: dimension,
          dealAnalysisView: view,
          dealAnalysisLimit: limit,
          offset: 0,
        })
      }
      onDealChange={(dealId) =>
        navigate(
          {
            ...location,
            dealId,
            invalidDealId: false,
            dealSection: "overview",
          },
          dealId === null,
        )
      }
      onSectionChange={(dealSection, replace = false) => navigate({ ...location, dealSection }, replace)}
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
    />
  );
}
