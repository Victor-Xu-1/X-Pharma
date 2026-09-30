import { contractRequest } from "../contract";
import type {
  EpidemiologyLinkedEntityRead,
  EpidemiologyObservationSearchItemRead,
  EpidemiologyObservationSearchResult,
  EpidemiologySavedSearchQuery,
  EpidemiologyTrendResult as GeneratedEpidemiologyTrendResult,
} from "../generated";
import { EpidemiologyService, MonitoringService } from "../generated";
import { effectiveSort, type SortCriterion } from "./sorting";

export type EpidemiologyLinkedEntity = EpidemiologyLinkedEntityRead;
export type EpidemiologyObservation = EpidemiologyObservationSearchItemRead;
export type EpidemiologySearchResult = EpidemiologyObservationSearchResult;
export type EpidemiologyTrendResult = GeneratedEpidemiologyTrendResult;
export interface EpidemiologyFacetCatalog {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  patient_populations: EpidemiologySearchResult["patient_populations"];
  warnings: string[];
}
export const epidemiologySortFields = [
  "period_end",
  "period_start",
  "disease",
  "measure",
  "value",
  "geography",
  "unit",
  "publisher",
  "sample_size",
] as const;
export type EpidemiologySortField = (typeof epidemiologySortFields)[number];

export type EpidemiologyFilters = {
  query: string;
  diseaseEntityId: string;
  measure: string;
  geography: string;
  unit: string;
  patientPopulationId: string;
  populationScope: string;
  ageGroup: string;
  sex: string;
  periodStartFrom: string;
  periodEndTo: string;
  sortBy: EpidemiologySortField;
  sortDirection: "asc" | "desc";
  sort?: SortCriterion<EpidemiologySortField>[];
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
};

export const epidemiologyKeys = {
  search: (filters: EpidemiologyFilters, offset: number) =>
    ["intelligence", "epidemiology", "search", filters, offset] as const,
  trend: (diseaseId: string, anchorObservationId: string, filters: EpidemiologyFilters) =>
    ["intelligence", "epidemiology", "trend", diseaseId, anchorObservationId, filters] as const,
  facetCatalog: () => ["intelligence", "epidemiology", "facet-catalog"] as const,
};

export async function loadEpidemiologyFacetCatalog(signal?: AbortSignal): Promise<EpidemiologyFacetCatalog> {
  const result = await contractRequest(
    EpidemiologyService.searchEpidemiologyObservationsApiV1EpidemiologyObservationsGet({
      limit: 1,
      offset: 0,
      sort: ["period_end:desc"],
    }),
    signal,
  );
  return {
    as_of: result.as_of,
    facets: result.facets,
    patient_populations: result.patient_populations,
    warnings: result.warnings,
  };
}

export function savedEpidemiologyQuery(filters: EpidemiologyFilters): EpidemiologySavedSearchQuery {
  return {
    q: filters.query.trim() || undefined,
    disease_entity_id: filters.diseaseEntityId || undefined,
    measure: (filters.measure || undefined) as EpidemiologySavedSearchQuery["measure"],
    geography: filters.geography || undefined,
    unit: filters.unit || undefined,
    patient_population_id: filters.patientPopulationId || undefined,
    population_scope: filters.populationScope || undefined,
    age_group: filters.ageGroup || undefined,
    sex: filters.sex || undefined,
    period_start_from: filters.periodStartFrom || undefined,
    period_end_to: filters.periodEndTo || undefined,
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
    sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: filters.displayMode,
    analysis_view: filters.analysisView,
  };
}

export function hasEpidemiologySearchFilter(filters: EpidemiologyFilters): boolean {
  const query = savedEpidemiologyQuery(filters);
  return Object.entries(query).some(
    ([key, value]) =>
      !["sort_by", "sort_direction", "sort", "display_mode", "analysis_view"].includes(key) && value !== undefined,
  );
}

export async function saveEpidemiologySearch({
  name,
  filters,
  shared,
  monitor,
}: {
  name: string;
  filters: EpidemiologyFilters;
  shared: boolean;
  monitor: boolean;
}): Promise<{ message: string }> {
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query_type: "epidemiology_search",
        query: savedEpidemiologyQuery(filters),
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
      return { message: `检索已保存，但监控未启用：${error instanceof Error ? error.message : "未知错误"}` };
    }
  }
  return { message: monitor ? "流行病学检索已保存并启用监控" : "流行病学检索已保存" };
}

export async function searchEpidemiology(
  filters: EpidemiologyFilters,
  offset: number,
  signal?: AbortSignal,
): Promise<EpidemiologySearchResult> {
  return contractRequest(
    EpidemiologyService.searchEpidemiologyObservationsApiV1EpidemiologyObservationsGet({
      q: filters.query.trim() || undefined,
      diseaseEntityId: filters.diseaseEntityId || undefined,
      measure: filters.measure || undefined,
      geography: filters.geography || undefined,
      unit: filters.unit || undefined,
      patientPopulationId: filters.patientPopulationId || undefined,
      populationScope: filters.populationScope || undefined,
      ageGroup: filters.ageGroup || undefined,
      sex: filters.sex || undefined,
      periodStartFrom: filters.periodStartFrom ? `${filters.periodStartFrom}T00:00:00Z` : undefined,
      periodEndTo: filters.periodEndTo ? `${filters.periodEndTo}T23:59:59Z` : undefined,
      sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      limit: 100,
      offset,
    }),
    signal,
  );
}

export async function loadEpidemiologyTrend(
  diseaseId: string,
  anchorObservationId: string,
  filters: EpidemiologyFilters,
  signal?: AbortSignal,
): Promise<EpidemiologyTrendResult> {
  return contractRequest(
    EpidemiologyService.getEpidemiologyTrendApiV1EpidemiologyTrendsDiseaseEntityIdGet({
      diseaseEntityId: diseaseId,
      measure: filters.measure || undefined,
      geography: filters.geography || undefined,
      unit: filters.unit || undefined,
      patientPopulationId: filters.patientPopulationId || undefined,
      populationScope: filters.populationScope || undefined,
      ageGroup: filters.ageGroup || undefined,
      sex: filters.sex || undefined,
      anchorObservationId,
      limit: 500,
    }),
    signal,
  );
}
