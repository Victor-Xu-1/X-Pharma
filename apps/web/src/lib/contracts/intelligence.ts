import { contractRequest } from "../contract";
import type { EntityRead, EntitySearchItemRead, EntityType, ReviewStatus, SearchResult } from "../generated";
import { EntitiesService, MonitoringService } from "../generated";
import { effectiveSort, type SortCriterion } from "./sorting";

const entityTypes = new Set<EntityType>([
  "drug",
  "target",
  "disease",
  "organization",
  "clinical_trial",
  "patent",
  "transaction",
  "product",
  "technology",
  "person",
]);

export const intelligenceKeys = {
  search: (
    query: string,
    entityTypes: readonly string[],
    reviewStatus: string,
    sortBy: EntitySearchSortField = "relevance",
    sortDirection: EntitySearchSortDirection = "desc",
    offset = 0,
    sort?: readonly SortCriterion<EntitySearchSortField>[],
    includeRelated = false,
  ) =>
    [
      "intelligence",
      "entities",
      { query, entityTypes, reviewStatus, sortBy, sortDirection, offset, sort, includeRelated },
    ] as const,
  suggestions: (query: string, entityTypes: readonly string[]) =>
    ["intelligence", "entity-suggestions", { query, entityTypes }] as const,
  lookup: (query: string, entityType: string) => ["intelligence", "entity-lookup", { query, entityType }] as const,
  lookupMany: (query: string, entityTypes: readonly string[]) =>
    ["intelligence", "entity-lookup-many", { query, entityTypes }] as const,
  entity: (entityId: string) => ["intelligence", "entity", entityId] as const,
};

export const entitySortFields = ["relevance", "name", "entity_type", "updated_at"] as const;
export type EntitySearchSortField = (typeof entitySortFields)[number];
export type EntitySearchSortDirection = "asc" | "desc";

export interface EntitySearchPageOptions {
  sortBy?: EntitySearchSortField;
  sortDirection?: EntitySearchSortDirection;
  sort?: SortCriterion<EntitySearchSortField>[];
  offset?: number;
  includeRelated?: boolean;
}

export type IntelligenceEntity = EntitySearchItemRead;

export type EntitySearchResult = Omit<SearchResult, "items" | "engine" | "facets" | "suggestions" | "took_ms"> & {
  items: IntelligenceEntity[];
  engine: string;
  facets: Record<string, Record<string, number>>;
  suggestions: string[];
  took_ms: number | null;
};

export function asEntityType(value: string): EntityType | undefined {
  return entityTypes.has(value as EntityType) ? (value as EntityType) : undefined;
}

export function asEntityTypes(values: readonly string[]): EntityType[] {
  return Array.from(new Set(values.filter((value) => entityTypes.has(value as EntityType)) as EntityType[])).sort();
}

export function asReviewStatus(value: string): ReviewStatus | undefined {
  return ["draft", "verified", "rejected", "superseded"].includes(value) ? (value as ReviewStatus) : undefined;
}

export async function searchEntities(
  query: string,
  entityTypes: readonly string[],
  reviewStatus: string,
  signal?: AbortSignal,
  options: EntitySearchPageOptions = {},
): Promise<EntitySearchResult> {
  const sortBy = options.sortBy ?? "relevance";
  const sortDirection = options.sortDirection ?? "desc";
  const sort = effectiveSort(options.sort, sortBy, sortDirection);
  const offset = Math.max(0, options.offset ?? 0);
  const normalizedTypes = asEntityTypes(entityTypes);
  const result = await contractRequest(
    EntitiesService.searchEntitiesApiV1EntitiesGet({
      q: query.trim() || undefined,
      entityType: normalizedTypes.length === 1 ? normalizedTypes[0] : undefined,
      entityTypes: normalizedTypes.length > 1 ? normalizedTypes : undefined,
      reviewStatus: asReviewStatus(reviewStatus),
      limit: 100,
      offset,
      sort: sort.map((criterion) => `${criterion.field}:${criterion.direction}`),
      includeRelated: options.includeRelated ?? false,
    }),
    signal,
  );
  return {
    ...result,
    engine: result.engine ?? "unknown",
    facets: result.facets ?? {},
    suggestions: result.suggestions ?? [],
    took_ms: result.took_ms ?? null,
    sort_by: result.sort_by ?? sortBy,
    sort_direction: result.sort_direction ?? sortDirection,
    sort: result.sort?.length ? result.sort : sort,
  };
}

export async function suggestEntities(
  query: string,
  entityTypes: readonly string[],
  signal?: AbortSignal,
): Promise<string[]> {
  const normalizedTypes = asEntityTypes(entityTypes);
  const result = await contractRequest(
    EntitiesService.suggestEntitiesApiV1EntitiesSuggestionsGet({
      q: query.trim(),
      entityType: normalizedTypes.length === 1 ? normalizedTypes[0] : undefined,
      entityTypes: normalizedTypes.length > 1 ? normalizedTypes : undefined,
      limit: 10,
    }),
    signal,
  );
  return result.suggestions;
}

export async function lookupEntities(
  query: string,
  entityType: string,
  signal?: AbortSignal,
): Promise<EntitySearchItemRead[]> {
  const result = await contractRequest(
    EntitiesService.searchEntitiesApiV1EntitiesGet({
      q: query.trim(),
      entityType: asEntityType(entityType),
      reviewStatus: "verified",
      limit: 10,
    }),
    signal,
  );
  return result.items;
}

export async function lookupEntityTypes(
  query: string,
  requestedEntityTypes: readonly string[],
  signal?: AbortSignal,
): Promise<EntitySearchItemRead[]> {
  const normalizedTypes = asEntityTypes(requestedEntityTypes);
  if (!normalizedTypes.length) return [];
  const result = await contractRequest(
    EntitiesService.searchEntitiesApiV1EntitiesGet({
      q: query.trim(),
      entityType: normalizedTypes.length === 1 ? normalizedTypes[0] : undefined,
      entityTypes: normalizedTypes.length > 1 ? normalizedTypes : undefined,
      reviewStatus: "verified",
      limit: 10,
    }),
    signal,
  );
  return result.items;
}

export async function getEntity(entityId: string, signal?: AbortSignal): Promise<EntityRead> {
  return contractRequest(EntitiesService.getEntityApiV1EntitiesEntityIdGet({ entityId }), signal);
}

export async function saveEntitySearch({
  name,
  query,
  entityTypes,
  reviewStatus,
  sortBy,
  sortDirection,
  sort,
  displayMode,
  analysisView,
  shared,
  monitor,
  includeRelated = false,
}: {
  name: string;
  query: string;
  entityTypes: readonly string[];
  reviewStatus: string;
  sortBy: EntitySearchSortField;
  sortDirection: EntitySearchSortDirection;
  sort?: SortCriterion<EntitySearchSortField>[];
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
  shared: boolean;
  monitor: boolean;
  includeRelated?: boolean;
}): Promise<{ message: string }> {
  const normalizedTypes = asEntityTypes(entityTypes);
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query: {
          q: query.trim() || undefined,
          entity_type: normalizedTypes.length === 1 ? normalizedTypes[0] : undefined,
          entity_types: normalizedTypes.length > 1 ? normalizedTypes : undefined,
          review_status: asReviewStatus(reviewStatus),
          include_related: includeRelated,
          sort_by: sortBy,
          sort_direction: sortDirection,
          sort: effectiveSort(sort, sortBy, sortDirection).map(
            (criterion) => `${criterion.field}:${criterion.direction}`,
          ),
          display_mode: displayMode === "landscape" ? "landscape" : undefined,
          analysis_view: displayMode === "landscape" && analysisView === "table" ? "table" : undefined,
        },
        visibility: shared ? "tenant" : "private",
      },
    }),
  );
  if (monitor) {
    try {
      await contractRequest(
        MonitoringService.createMonitoringTopicApiV1MonitoringTopicsPost({
          requestBody: { name: name.trim(), saved_search_id: saved.id },
        }),
      );
    } catch (error) {
      const reason = error instanceof Error ? error.message : "未知错误";
      return { message: `检索已保存，但监控未启用：${reason}` };
    }
  }
  return { message: monitor ? "基础查询检索已保存并启用监控" : "基础查询检索已保存" };
}
