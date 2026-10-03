import { lazy } from "react";
import { workspaceUrl } from "../../lib/workspaceRouting";
import type { ResearchRouteContext } from "./routeContext";

const CollectionsView = lazy(() =>
  import("../../views/CollectionsView").then((module) => ({ default: module.CollectionsView })),
);

export function CollectionsRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openEntity, openDrugById } = context;
  return (
    <CollectionsView
      activeCollectionId={location.collectionId ?? null}
      comparedEntityIds={location.collectionCompareEntityIds ?? []}
      onLocationChange={(collectionId, collectionCompareEntityIds, replace = false) =>
        navigate(
          {
            ...location,
            collectionId,
            invalidCollectionId: false,
            collectionCompareEntityIds,
          },
          replace,
          true,
        )
      }
      onOpenEntity={(entity) =>
        entity.entity_type === "drug" ? openDrugById(entity.id, workspaceUrl(location)) : openEntity(entity)
      }
    />
  );
}
