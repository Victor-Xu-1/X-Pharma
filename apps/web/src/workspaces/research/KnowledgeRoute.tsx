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
      initialPageId={location.knowledgePageId}
      initialPanel={location.knowledgePanel ?? "document"}
      initialVersionNumber={location.knowledgeVersionNumber}
      invalidPageId={location.invalidKnowledgePageId}
      onLocationChange={(next) =>
        navigate({
          ...location,
          view: "knowledge",
          query: next.query,
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
