import { lazy } from "react";
import type { ResearchRouteContext } from "./routeContext";

const EvidenceView = lazy(() =>
  import("../../views/EvidenceView").then((module) => ({ default: module.EvidenceView })),
);

export function EvidenceRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate } = context;
  return (
    <EvidenceView
      initialQuery={location.query}
      initialDatasetKeys={location.evidenceDatasetKeys}
      initialDocumentId={location.evidenceDocumentId}
      initialChunkIndex={location.evidenceChunkIndex}
      onLocationChange={(next) =>
        navigate({
          ...location,
          view: "evidence",
          query: next.query,
          entityId: null,
          invalidEntityId: false,
          evidenceDatasetKeys: next.datasetKeys,
          evidenceDocumentId: next.documentId,
          evidenceChunkIndex: next.chunkIndex,
        })
      }
    />
  );
}
