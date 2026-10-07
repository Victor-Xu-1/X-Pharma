import { lazy } from "react";
import type { EntitySearchSortField } from "../../lib/contracts/intelligence";
import type { SortCriterion } from "../../lib/contracts/sorting";
import type { ResearchRouteContext } from "./routeContext";

const ExplorerView = lazy(() =>
  import("../../views/ExplorerView").then((module) => ({ default: module.ExplorerView })),
);

export function ExplorerRoute({ context }: { context: ResearchRouteContext }) {
  const { location, selectedEntity, setSelectedEntity, routeEntity, navigate, openEntity, openTargetPipelineById } =
    context;
  return (
    <ExplorerView
      initialQuery={location.query}
      initialEntityType={location.entityType}
      initialEntityTypes={location.entityTypes ?? []}
      initialIncludeRelated={location.entityIncludeRelated ?? true}
      initialReviewStatus={location.reviewStatus}
      initialSortBy={location.entitySortBy ?? "relevance"}
      initialSortDirection={location.entitySortDirection ?? "desc"}
      initialSort={location.entitySort as SortCriterion<EntitySearchSortField>[] | undefined}
      initialOffset={location.offset ?? 0}
      initialDisplayMode={location.explorerDisplayMode ?? "list"}
      initialAnalysisView={location.explorerAnalysisView ?? "chart"}
      initialSelectedEntityId={location.entityId}
      invalidSelectedEntityId={location.invalidEntityId}
      selectedEntity={
        routeEntity.data?.id === location.entityId
          ? routeEntity.data
          : selectedEntity?.id === location.entityId
            ? selectedEntity
            : null
      }
      selectedEntityLoading={routeEntity.isFetching && selectedEntity?.id !== location.entityId}
      selectedEntityError={routeEntity.error instanceof Error ? routeEntity.error.message : ""}
      onSearchChange={(query, entityTypes, reviewStatus, sortBy, sortDirection, offset, sort, includeRelated) =>
        navigate(
          {
            ...location,
            workbench: "research",
            view: "explorer",
            query,
            entityType: entityTypes.length === 1 ? (entityTypes[0] ?? "") : "",
            entityTypes,
            entityIncludeRelated: includeRelated ?? location.entityIncludeRelated ?? true,
            reviewStatus,
            entitySort: sort,
            entitySortBy: sortBy,
            entitySortDirection: sortDirection,
            offset,
            entityId: null,
            invalidEntityId: false,
          },
          true,
          // Controlled inputs must commit immediately; keep other dense-view updates transitional.
          includeRelated !== undefined && includeRelated !== (location.entityIncludeRelated ?? true),
        )
      }
      onDisplayModeChange={(explorerDisplayMode) =>
        navigate({ ...location, explorerDisplayMode, offset: 0, entityId: null, invalidEntityId: false })
      }
      onAnalysisViewChange={(explorerAnalysisView) => navigate({ ...location, explorerAnalysisView })}
      onOpenEntity={openEntity}
      onOpenTargetPipeline={openTargetPipelineById}
      onSelectedEntityChange={(entity) => {
        navigate({ ...location, entityId: entity?.id ?? null, invalidEntityId: false });
        setSelectedEntity(entity);
      }}
      onOpenSpecializedSearch={navigate}
    />
  );
}
