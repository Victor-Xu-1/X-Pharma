import { lazy } from "react";
import type { PipelineResultGrain, PipelineSearchFilters } from "../../lib/contracts/pipeline";
import { workspaceUrl } from "../../lib/workspaceRouting";
import type { ResearchRouteContext } from "./routeContext";

const PipelineView = lazy(() =>
  import("../../views/PipelineView").then((module) => ({ default: module.PipelineView })),
);

export function PipelineRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <PipelineView
      displayMode={location.pipelineDisplayMode ?? "list"}
      resultGrain={
        location.pipelineResultGrain ?? (location.pipelineTargetEntityId ? ("drug" as const) : ("program" as const))
      }
      analysisDimension={location.pipelineAnalysisDimension ?? "all"}
      analysisView={location.pipelineAnalysisView ?? "chart"}
      analysisLimit={location.pipelineAnalysisLimit ?? 8}
      analysisStageScope={location.pipelineAnalysisStageScope ?? "overall"}
      targetAggregation={location.pipelineTargetAggregation ?? "all"}
      initialFilters={{
        query: location.query,
        modalities: location.pipelineModalities ?? [],
        innovationTypes: location.pipelineInnovationTypes ?? [],
        therapeuticAreas: location.pipelineTherapeuticAreas ?? [],
        drugCategories: location.pipelineDrugCategories ?? [],
        programStatus: location.pipelineProgramStatus ?? "",
        organizationRole: location.pipelineOrganizationRole ?? "",
        organizationType: location.pipelineOrganizationType ?? "",
        organizationCountryRegion: location.pipelineOrganizationCountryRegion ?? "",
        phase: location.phase ?? "",
        geography: location.geography ?? "",
        statusDateFrom: location.pipelineStatusDateFrom ?? "",
        statusDateTo: location.pipelineStatusDateTo ?? "",
        drugEntityId: location.pipelineDrugEntityId ?? "",
        targetEntityId: location.pipelineTargetEntityId ?? "",
        targetCombinationKey: location.pipelineTargetCombinationKey ?? "",
        diseaseEntityId: location.pipelineDiseaseEntityId ?? "",
        organizationEntityId: location.pipelineOrganizationEntityId ?? "",
        globalPhase: location.pipelineGlobalPhase ?? "",
        chinaPhase: location.pipelineChinaPhase ?? "",
        globalPhaseStartedFrom: location.pipelineGlobalPhaseStartedFrom ?? "",
        globalPhaseStartedTo: location.pipelineGlobalPhaseStartedTo ?? "",
        chinaPhaseStartedFrom: location.pipelineChinaPhaseStartedFrom ?? "",
        chinaPhaseStartedTo: location.pipelineChinaPhaseStartedTo ?? "",
        developmentRightsRegion: location.pipelineDevelopmentRightsRegion ?? "",
        commercializationRightsRegion: location.pipelineCommercializationRightsRegion ?? "",
        programTags: location.pipelineProgramTags ?? [],
        milestoneType: location.pipelineMilestoneType ?? "",
        milestoneFrom: location.pipelineMilestoneFrom ?? "",
        milestoneTo: location.pipelineMilestoneTo ?? "",
        hasClinicalResults: location.pipelineHasClinicalResults ?? "",
        clinicalResultEvaluation: location.pipelineClinicalResultEvaluation ?? "",
        hasDeal: location.pipelineHasDeal ?? "",
        dealCurrency: location.pipelineDealCurrency ?? "",
        dealTotalPotentialAmountMin: location.pipelineDealTotalPotentialAmountMin ?? "",
        dealTotalPotentialAmountMax: location.pipelineDealTotalPotentialAmountMax ?? "",
        sortBy: (location.pipelineSortBy ?? "status_date") as PipelineSearchFilters["sortBy"],
        sortDirection: location.pipelineSortDirection ?? "desc",
        sort: location.pipelineSort as PipelineSearchFilters["sort"],
        offset: location.offset ?? 0,
      }}
      onSearchChange={(filters) =>
        navigate({
          workbench: "research",
          view: "pipeline",
          query: filters.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          pipelineModalities: filters.modalities,
          pipelineInnovationTypes: filters.innovationTypes,
          pipelineTherapeuticAreas: filters.therapeuticAreas,
          pipelineDrugCategories: filters.drugCategories,
          pipelineProgramStatus: filters.programStatus,
          pipelineOrganizationRole: filters.organizationRole,
          pipelineOrganizationType: filters.organizationType,
          pipelineOrganizationCountryRegion: filters.organizationCountryRegion,
          phase: filters.phase,
          geography: filters.geography,
          pipelineStatusDateFrom: filters.statusDateFrom,
          pipelineStatusDateTo: filters.statusDateTo,
          pipelineDrugEntityId: filters.drugEntityId,
          pipelineTargetEntityId: filters.targetEntityId,
          pipelineTargetCombinationKey: filters.targetCombinationKey,
          pipelineDiseaseEntityId: filters.diseaseEntityId,
          pipelineOrganizationEntityId: filters.organizationEntityId,
          pipelineGlobalPhase: filters.globalPhase,
          pipelineChinaPhase: filters.chinaPhase,
          pipelineGlobalPhaseStartedFrom: filters.globalPhaseStartedFrom,
          pipelineGlobalPhaseStartedTo: filters.globalPhaseStartedTo,
          pipelineChinaPhaseStartedFrom: filters.chinaPhaseStartedFrom,
          pipelineChinaPhaseStartedTo: filters.chinaPhaseStartedTo,
          pipelineDevelopmentRightsRegion: filters.developmentRightsRegion,
          pipelineCommercializationRightsRegion: filters.commercializationRightsRegion,
          pipelineProgramTags: filters.programTags,
          pipelineMilestoneType: filters.milestoneType,
          pipelineMilestoneFrom: filters.milestoneFrom,
          pipelineMilestoneTo: filters.milestoneTo,
          pipelineHasClinicalResults: filters.hasClinicalResults,
          pipelineClinicalResultEvaluation: filters.clinicalResultEvaluation,
          pipelineHasDeal: filters.hasDeal,
          pipelineDealCurrency: filters.dealCurrency,
          pipelineDealTotalPotentialAmountMin: filters.dealTotalPotentialAmountMin,
          pipelineDealTotalPotentialAmountMax: filters.dealTotalPotentialAmountMax,
          pipelineSort: filters.sort,
          pipelineSortBy: filters.sortBy,
          pipelineSortDirection: filters.sortDirection,
          pipelineDisplayMode: location.pipelineDisplayMode ?? "list",
          pipelineResultGrain:
            location.pipelineResultGrain ?? (filters.targetEntityId ? ("drug" as const) : ("program" as const)),
          pipelineAnalysisDimension: location.pipelineAnalysisDimension ?? "all",
          pipelineAnalysisView: location.pipelineAnalysisView ?? "chart",
          pipelineAnalysisLimit: location.pipelineAnalysisLimit ?? 8,
          pipelineAnalysisStageScope: location.pipelineAnalysisStageScope ?? "overall",
          pipelineTargetAggregation: location.pipelineTargetAggregation ?? "all",
          offset: filters.offset,
        })
      }
      onDisplayModeChange={(displayMode) => navigate({ ...location, pipelineDisplayMode: displayMode, offset: 0 })}
      onResultGrainChange={(resultGrain: PipelineResultGrain) =>
        navigate({ ...location, pipelineResultGrain: resultGrain, offset: 0 })
      }
      onAnalysisChange={(analysis) =>
        navigate({
          ...location,
          pipelineDisplayMode: "landscape",
          pipelineAnalysisDimension: analysis.dimension,
          pipelineAnalysisView: analysis.view,
          pipelineAnalysisLimit: analysis.limit,
          pipelineAnalysisStageScope: analysis.stageScope,
          pipelineTargetAggregation: analysis.targetAggregation,
          offset: 0,
        })
      }
      onOpenDrug={(entityId) => openDrugById(entityId, workspaceUrl(location))}
      onOpenEntity={openEntityById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
      onOpenTrialsForDrug={(drugEntityId) =>
        navigate({
          workbench: "research",
          view: "trials",
          query: "",
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          trialRoleEntityId: drugEntityId,
          trialRoleEntityRole: "",
          trialId: null,
          invalidTrialId: false,
          trialSection: "overview",
          offset: 0,
        })
      }
      onOpenDealsForDrug={(drugEntityId) =>
        navigate({
          workbench: "research",
          view: "deals",
          query: "",
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          dealAssetEntityId: drugEntityId,
          dealId: null,
          invalidDealId: false,
          dealSection: "overview",
          offset: 0,
        })
      }
    />
  );
}
