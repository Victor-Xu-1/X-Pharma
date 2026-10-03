import { lazy } from "react";
import type { NewsSearchFilters } from "../../lib/contracts/news";
import type { ResearchRouteContext } from "./routeContext";

const NewsView = lazy(() => import("../../views/NewsView").then((module) => ({ default: module.NewsView })));

export function NewsRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <NewsView
      initialFilters={{
        query: location.query,
        entityId: location.newsEntityId ?? "",
        eventType: location.newsEventType ?? "",
        publisher: location.newsPublisher ?? "",
        language: location.newsLanguage ?? "",
        venue: location.newsVenue ?? "",
        publishedFrom: location.newsPublishedFrom ?? "",
        publishedTo: location.newsPublishedTo ?? "",
        contentScope: location.newsContentScope ?? "",
        displayMode: location.newsDisplayMode ?? "list",
        analysisView: location.newsAnalysisView ?? "chart",
        sortBy: (location.newsSortBy ?? "published_at") as NewsSearchFilters["sortBy"],
        sortDirection: location.newsSortDirection ?? "desc",
        sort: location.newsSort as NewsSearchFilters["sort"],
      }}
      initialOffset={location.offset ?? 0}
      selectedNewsEventId={location.newsEventId ?? null}
      onSearchChange={(filters, offset) =>
        navigate({
          workbench: "research",
          view: "news",
          query: filters.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          newsEntityId: filters.entityId,
          newsEventType: filters.eventType,
          newsAnalysisView: filters.analysisView,
          newsPublisher: filters.publisher,
          newsLanguage: filters.language,
          newsVenue: filters.venue,
          newsPublishedFrom: filters.publishedFrom,
          newsPublishedTo: filters.publishedTo,
          newsContentScope: filters.contentScope,
          newsDisplayMode: filters.displayMode,
          newsSort: filters.sort,
          newsSortBy: filters.sortBy,
          newsSortDirection: filters.sortDirection,
          newsEventId: null,
          invalidNewsEventId: false,
          offset,
        })
      }
      onNewsEventChange={(newsEventId) =>
        navigate(
          {
            ...location,
            newsEventId,
            invalidNewsEventId: false,
          },
          newsEventId === null,
        )
      }
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
    />
  );
}
