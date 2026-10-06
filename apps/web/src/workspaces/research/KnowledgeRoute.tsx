import { lazy } from "react";
import type { ResearchRouteContext } from "./routeContext";

const KnowledgeView = lazy(() =>
  import("../../views/KnowledgeView").then((module) => ({ default: module.KnowledgeView })),
);

export function KnowledgeRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate } = context;
  return (
    <KnowledgeView
      initialQuery={location.query}
      initialOffset={location.offset ?? 0}
      initialPageType={location.knowledgePageType ?? ""}
      initialSortBy={location.knowledgeSortBy ?? "title"}
      initialSortDirection={location.knowledgeSortDirection ?? "asc"}
      initialPageId={location.knowledgePageId}
      initialPanel={location.knowledgePanel ?? "document"}
      initialVersionNumber={location.knowledgeVersionNumber}
      invalidPageId={location.invalidKnowledgePageId}
      onLocationChange={(next) =>
        navigate({
          ...location,
          view: "knowledge",
          query: next.query,
          offset: next.offset,
          knowledgePageType: next.pageType,
          knowledgeSortBy: next.sortBy,
          knowledgeSortDirection: next.sortDirection,
          entityId: null,
          invalidEntityId: false,
          knowledgePageId: next.pageId,
          invalidKnowledgePageId: false,
          knowledgePanel: next.panel,
          knowledgeVersionNumber: next.versionNumber,
        })
      }
    />
  );
}
