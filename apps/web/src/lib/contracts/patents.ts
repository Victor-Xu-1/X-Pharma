import { contractRequest } from "../contract";
import type { PatentFamilySearchItemRead, PatentFamilySearchResult, PatentSavedSearchQuery } from "../generated";
import { PatentsService } from "../generated";
import { type SavedSearchCreationOutcome, saveAndSubscribeSearch } from "./savedSearchCreation";
import { effectiveSort, type SortCriterion } from "./sorting";

export const patentSortFields = ["priority_date", "family_identifier", "legal_status", "expiration_date"] as const;
export type PatentSortField = (typeof patentSortFields)[number];
export type SortDirection = "asc" | "desc";

export const patentLegalStatusLabels: Readonly<Record<string, string>> = {
  ACTIVE: "有效",
  PENDING: "审查中",
  GRANTED: "授权",
  EXPIRED: "到期",
  LAPSED: "失效",
  REVOKED: "撤销",
  WITHDRAWN: "撤回",
};

export interface PatentFacetCatalog {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  warnings: string[];
}

export interface PatentSavedSearchInput {
  query: string;
  entityId: string;
  applicant: string;
  legalStatus: string;
  priorityFrom: string;
  priorityTo: string;
  expirationFrom: string;
  expirationTo: string;
  sortBy: PatentSortField;
  sortDirection: SortDirection;
  sort?: SortCriterion<PatentSortField>[];
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
}

export type PatentSearchFilters = Pick<
  PatentSavedSearchInput,
  "query" | "entityId" | "applicant" | "legalStatus" | "priorityFrom" | "priorityTo" | "expirationFrom" | "expirationTo"
>;

export const emptyPatentSearchFilters: PatentSearchFilters = {
  query: "",
  entityId: "",
  applicant: "",
  legalStatus: "",
  priorityFrom: "",
  priorityTo: "",
  expirationFrom: "",
  expirationTo: "",
};

export function validatePatentSearchFilters(filters: PatentSearchFilters) {
  if (filters.priorityFrom && filters.priorityTo && filters.priorityFrom > filters.priorityTo)
    return "优先权日期起始值不能晚于结束值" as const;
  if (filters.expirationFrom && filters.expirationTo && filters.expirationFrom > filters.expirationTo)
    return "预计到期日期起始值不能晚于结束值" as const;
  return null;
}

function savedPatentQuery(input: PatentSavedSearchInput): PatentSavedSearchQuery {
  return {
    q: input.query.trim() || undefined,
    entity_id: input.entityId || undefined,
    applicant: input.applicant || undefined,
    legal_status: input.legalStatus || undefined,
    priority_from: input.priorityFrom || undefined,
    priority_to: input.priorityTo || undefined,
    expiration_from: input.expirationFrom || undefined,
    expiration_to: input.expirationTo || undefined,
    sort_by: input.sortBy,
    sort_direction: input.sortDirection,
    sort: effectiveSort(input.sort, input.sortBy, input.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: input.displayMode,
    analysis_view: input.analysisView,
  };
}

export function hasPatentSearchFilter(input: PatentSavedSearchInput): boolean {
  const query = savedPatentQuery(input);
  return Object.entries(query).some(
    ([key, value]) =>
      !["sort_by", "sort_direction", "sort", "display_mode", "analysis_view"].includes(key) && value !== undefined,
  );
}

export async function savePatentSearch({
  name,
  input,
  shared,
  monitor,
}: {
  name: string;
  input: PatentSavedSearchInput;
  shared: boolean;
  monitor: boolean;
}): Promise<SavedSearchCreationOutcome> {
  return saveAndSubscribeSearch(
    {
      name: name.trim(),
      query_type: "patent_search",
      query: savedPatentQuery(input),
      visibility: shared ? "tenant" : "private",
    },
    monitor,
  );
}

export const patentKeys = {
  search: (input: PatentSavedSearchInput, offset: number) => ["intelligence", "patents", input, offset] as const,
  detail: (patentId: string) => ["intelligence", "patents", "detail", patentId] as const,
  facetCatalog: () => ["intelligence", "patents", "facet-catalog"] as const,
};

export async function loadPatentFacetCatalog(signal?: AbortSignal): Promise<PatentFacetCatalog> {
  const result = await contractRequest(
    PatentsService.searchPatentFamiliesApiV1PatentFamiliesGet({
      limit: 1,
      offset: 0,
      sort: ["priority_date:desc"],
    }),
    signal,
  );
  return { as_of: result.as_of, facets: result.facets, warnings: result.warnings };
}

export async function loadPatentFamilyDetail(
  familyId: string,
  signal?: AbortSignal,
): Promise<PatentFamilySearchItemRead> {
  return contractRequest(PatentsService.getPatentFamilyApiV1PatentFamiliesFamilyIdGet({ familyId }), signal);
}

function startOfDay(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function endOfDay(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

export async function searchPatentFamilies(
  input: PatentSavedSearchInput,
  offset: number,
  signal?: AbortSignal,
): Promise<PatentFamilySearchResult> {
  return contractRequest(
    PatentsService.searchPatentFamiliesApiV1PatentFamiliesGet({
      q: input.query.trim() || undefined,
      entityId: input.entityId || undefined,
      applicant: input.applicant || undefined,
      legalStatus: input.legalStatus || undefined,
      priorityFrom: startOfDay(input.priorityFrom),
      priorityTo: endOfDay(input.priorityTo),
      expirationFrom: startOfDay(input.expirationFrom),
      expirationTo: endOfDay(input.expirationTo),
      sort: effectiveSort(input.sort, input.sortBy, input.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      limit: 100,
      offset,
    }),
    signal,
  );
}
