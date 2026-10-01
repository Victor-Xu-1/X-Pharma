import { lazy } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { workspaceUrl } from "../../lib/workspaceRouting";
import { locationWithPipelineFilters, pipelineFiltersFromLocation, researchReturnLabel } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

const TargetView = lazy(() => import("../../views/TargetView").then((module) => ({ default: module.TargetView })));

export function TargetRoute({ context }: { context: ResearchRouteContext }) {
  const {
    location,
    selectedEntity,
    activeReturnLocation,
    routeEntity,
    navigate,
    openDrugById,
    openEntityById,
    openTargetById,
    openDiseaseById,
    openOrganizationById,
    openTrialById,
    openDealById,
    openPatentFamilyById,
    openRegulatoryEventById,
    openNewsEventById,
  } = context;
  return routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
    <Spinner label="正在恢复靶点深链接" />
  ) : location.invalidEntityId || routeEntity.error ? (
    <ErrorState
      message={
        location.invalidEntityId
          ? "链接中的实体 ID 无效"
          : routeEntity.error instanceof Error
            ? routeEntity.error.message
            : "靶点链接加载失败"
      }
      retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
    />
  ) : (
    <TargetView
      target={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
      activeSection={location.targetSection ?? "overview"}
      onSectionChange={(targetSection) => navigate({ ...location, targetSection })}
      initialPipelineFilters={pipelineFiltersFromLocation(location, location.entityId ?? "")}
      onPipelineSearchChange={(filters) => navigate(locationWithPipelineFilters(location, filters), true)}
      onPipelineLandscapeFilterApply={(filters, targetPipelineDisplayMode) =>
        navigate({
          ...locationWithPipelineFilters(location, filters),
          targetPipelineDisplayMode,
          offset: 0,
        })
      }
      initialPipelineDisplayMode={location.targetPipelineDisplayMode ?? "drug"}
      onPipelineDisplayModeChange={(targetPipelineDisplayMode) =>
        navigate({
          ...location,
          targetPipelineDisplayMode,
          offset: 0,
        })
      }
      initialPipelineAnalysis={{
        dimension: location.pipelineAnalysisDimension ?? "all",
        view: location.pipelineAnalysisView ?? "chart",
        limit: location.pipelineAnalysisLimit ?? 20,
        stageScope: location.pipelineAnalysisStageScope ?? "overall",
        targetAggregation: location.pipelineTargetAggregation ?? "all",
      }}
      onPipelineAnalysisChange={(analysis) =>
        navigate({
          ...location,
          targetPipelineDisplayMode: "landscape",
          pipelineAnalysisDimension: analysis.dimension,
          pipelineAnalysisView: analysis.view,
          pipelineAnalysisLimit: analysis.limit,
          pipelineAnalysisStageScope: analysis.stageScope,
          pipelineTargetAggregation: analysis.targetAggregation,
          offset: 0,
        })
      }
      onOpenEntity={openEntityById}
      onOpenDrug={(entityId) => openDrugById(entityId, workspaceUrl(location))}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
      onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
      onOpenPatent={openPatentFamilyById}
      onOpenDeal={openDealById}
      onOpenRegulatoryEvent={openRegulatoryEventById}
      onOpenNewsEvent={openNewsEventById}
      returnLabel={researchReturnLabel(activeReturnLocation)}
      onReturn={activeReturnLocation ? () => navigate(activeReturnLocation, true, true) : undefined}
      onOpenEvidence={(query) =>
        navigate({
          workbench: "research",
          view: "evidence",
          query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          evidenceDatasetKeys: [],
          evidenceDocumentId: null,
          evidenceChunkIndex: null,
        })
      }
      onOpenComparison={(collectionId, entityIds) =>
        navigate(
          {
            ...location,
            view: "collections",
            query: "",
            entityType: "",
            reviewStatus: "",
            entityId: null,
            invalidEntityId: false,
            collectionId,
            invalidCollectionId: false,
            collectionCompareEntityIds: entityIds.slice(0, 4),
          },
          false,
          true,
        )
      }
    />
  );
}
