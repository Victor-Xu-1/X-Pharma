import { contractRequest } from "../contract";
import type { NewsEventSearchItemRead, NewsEventSearchResult, NewsSavedSearchQuery } from "../generated";
import { NewsService } from "../generated";
import { type SavedSearchCreationOutcome, saveAndSubscribeSearch } from "./savedSearchCreation";
import { effectiveSort, type SortCriterion } from "./sorting";

export const newsSortFields = ["published_at", "title", "event_type", "publisher", "venue"] as const;
export type NewsSortField = (typeof newsSortFields)[number];

export interface NewsSearchFilters {
  query: string;
  entityId: string;
  eventType: string;
  publisher: string;
  language: string;
  venue: string;
  publishedFrom: string;
  publishedTo: string;
  contentScope: "" | "research";
  displayMode: "list" | "timeline" | "landscape";
  analysisView: "chart" | "table";
  sortBy: NewsSortField;
  sortDirection: "asc" | "desc";
  sort?: SortCriterion<NewsSortField>[];
}

export interface NewsFacetCatalog {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  warnings: string[];
}

export function validateNewsSearchFilters(
  filters: Pick<NewsSearchFilters, "publishedFrom" | "publishedTo">,
): string | null {
  return filters.publishedFrom && filters.publishedTo && filters.publishedFrom > filters.publishedTo
    ? "发布日期起始值不能晚于结束值"
    : null;
}

export const newsKeys = {
  search: (filters: NewsSearchFilters, offset: number) => ["intelligence", "news", filters, offset] as const,
  detail: (eventId: string) => ["intelligence", "news", "detail", eventId] as const,
  facetCatalog: () => ["intelligence", "news", "facet-catalog"] as const,
};

export async function loadNewsFacetCatalog(signal?: AbortSignal): Promise<NewsFacetCatalog> {
  const result = await contractRequest(
    NewsService.searchNewsEventsApiV1NewsEventsGet({
      limit: 1,
      offset: 0,
      sort: ["published_at:desc"],
    }),
    signal,
  );
  return { as_of: result.as_of, facets: result.facets, warnings: result.warnings };
}

export function savedNewsQuery(filters: NewsSearchFilters): NewsSavedSearchQuery {
  return {
    q: filters.query.trim() || undefined,
    entity_id: filters.entityId || undefined,
    event_type: (filters.eventType || undefined) as NewsSavedSearchQuery["event_type"],
    publisher: filters.publisher.trim() || undefined,
    language: filters.language || undefined,
    venue: filters.venue.trim() || undefined,
    published_from: filters.publishedFrom || undefined,
    published_to: filters.publishedTo || undefined,
    content_scope: filters.contentScope || undefined,
    display_mode: filters.displayMode,
    analysis_view: filters.analysisView,
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
    sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
  };
}

export function hasNewsSearchFilter(filters: NewsSearchFilters): boolean {
  const query = savedNewsQuery(filters);
  return Object.entries(query).some(
    ([key, value]) =>
      !["display_mode", "analysis_view", "sort_by", "sort_direction", "sort"].includes(key) && value !== undefined,
  );
}

export async function saveNewsSearch({
  name,
  filters,
  shared,
  monitor,
}: {
  name: string;
  filters: NewsSearchFilters;
  shared: boolean;
  monitor: boolean;
}): Promise<SavedSearchCreationOutcome> {
  return saveAndSubscribeSearch(
    {
      name: name.trim(),
      query_type: "news_search",
      query: savedNewsQuery(filters),
      visibility: shared ? "tenant" : "private",
    },
    monitor,
  );
}

export async function loadNewsEventDetail(eventId: string, signal?: AbortSignal): Promise<NewsEventSearchItemRead> {
  return contractRequest(NewsService.getNewsEventApiV1NewsEventsEventIdGet({ eventId }), signal);
}

export async function searchNewsEvents(
  filters: NewsSearchFilters,
  offset: number,
  signal?: AbortSignal,
): Promise<NewsEventSearchResult> {
  return contractRequest(
    NewsService.searchNewsEventsApiV1NewsEventsGet({
      q: filters.query.trim() || undefined,
      entityId: filters.entityId || undefined,
      eventType: filters.eventType || undefined,
      publisher: filters.publisher || undefined,
      language: filters.language || undefined,
      venue: filters.venue || undefined,
      contentScope: filters.contentScope || undefined,
      publishedFrom: filters.publishedFrom || undefined,
      publishedTo: filters.publishedTo || undefined,
      sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      limit: 100,
      offset,
    }),
    signal,
  );
}
