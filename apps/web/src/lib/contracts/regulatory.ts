import { contractRequest } from "../contract";
import type {
  RegulatoryDesignationType,
  RegulatoryEventSearchItemRead,
  RegulatoryEventSearchResult,
  RegulatoryLabelChangeType,
  RegulatorySafetySeverity,
  RegulatorySafetySignalType,
  RegulatorySafetyStatus,
  RegulatorySavedSearchQuery,
} from "../generated";
import { MonitoringService, RegulatoryService } from "../generated";
import { effectiveSort, type SortCriterion } from "./sorting";

export const regulatorySortFields = [
  "decision_date",
  "title",
  "agency",
  "jurisdiction",
  "event_type",
  "status",
  "subject",
  "source_updated_at",
] as const;
export type RegulatorySortField = (typeof regulatorySortFields)[number];

export interface RegulatorySearchFilters {
  query: string;
  agency: string;
  jurisdiction: string;
  eventType: string;
  status: string;
  designationType: string;
  labelChangeType: string;
  boxedWarning: string;
  safetySignalType: string;
  safetySeverity: string;
  safetyStatus: string;
  decisionFrom: string;
  decisionTo: string;
  sourceUpdatedFrom: string;
  sourceUpdatedTo: string;
  sortBy: RegulatorySortField;
  sortDirection: "asc" | "desc";
  sort?: SortCriterion<RegulatorySortField>[];
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
}

export interface RegulatoryFacetCatalog {
  as_of: string;
  facets: Record<string, Record<string, number>>;
  warnings: string[];
}

export const emptyRegulatorySearchFilters: RegulatorySearchFilters = {
  query: "",
  agency: "",
  jurisdiction: "",
  eventType: "",
  status: "",
  designationType: "",
  labelChangeType: "",
  boxedWarning: "",
  safetySignalType: "",
  safetySeverity: "",
  safetyStatus: "",
  decisionFrom: "",
  decisionTo: "",
  sourceUpdatedFrom: "",
  sourceUpdatedTo: "",
  sortBy: "decision_date",
  sortDirection: "desc",
  sort: [{ field: "decision_date", direction: "desc" }],
  displayMode: "list",
  analysisView: "chart",
};

export function validateRegulatorySearchFilters(filters: RegulatorySearchFilters): string | null {
  if (filters.decisionFrom && filters.decisionTo && filters.decisionFrom > filters.decisionTo) {
    return "监管决定日期起始值不能晚于结束值";
  }
  if (filters.sourceUpdatedFrom && filters.sourceUpdatedTo && filters.sourceUpdatedFrom > filters.sourceUpdatedTo) {
    return "来源更新日期起始值不能晚于结束值";
  }
  return null;
}

const designationTypes = new Set<RegulatoryDesignationType>([
  "breakthrough_therapy",
  "fast_track",
  "priority_review",
  "accelerated_approval",
  "orphan_drug",
  "prime",
  "sakigake",
  "conditional_marketing_authorisation",
  "other",
]);
const labelChangeTypes = new Set<RegulatoryLabelChangeType>([
  "initial_label",
  "indication_expansion",
  "population_expansion",
  "restriction",
  "dosing_update",
  "administration_update",
  "safety_update",
  "boxed_warning",
  "contraindication",
  "other",
]);
const safetySignalTypes = new Set<RegulatorySafetySignalType>([
  "adverse_event",
  "boxed_warning",
  "contraindication",
  "risk_management",
  "recall",
  "clinical_hold",
  "postmarketing_requirement",
  "other",
]);
const safetySeverities = new Set<RegulatorySafetySeverity>([
  "informational",
  "moderate",
  "serious",
  "severe",
  "life_threatening",
  "fatal",
  "unknown",
]);
const safetyStatuses = new Set<RegulatorySafetyStatus>([
  "detected",
  "under_evaluation",
  "confirmed",
  "monitoring",
  "resolved",
  "withdrawn",
  "unknown",
]);

function enumValue<T extends string>(value: string, values: ReadonlySet<T>): T | undefined {
  return values.has(value as T) ? (value as T) : undefined;
}

function boxedWarning(value: string): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

export function savedRegulatoryQuery(filters: RegulatorySearchFilters): RegulatorySavedSearchQuery {
  return {
    q: filters.query.trim() || undefined,
    agency: filters.agency || undefined,
    jurisdiction: filters.jurisdiction || undefined,
    event_type: filters.eventType || undefined,
    status: filters.status || undefined,
    designation_type: enumValue(filters.designationType, designationTypes),
    label_change_type: enumValue(filters.labelChangeType, labelChangeTypes),
    has_boxed_warning: boxedWarning(filters.boxedWarning),
    safety_signal_type: enumValue(filters.safetySignalType, safetySignalTypes),
    safety_severity: enumValue(filters.safetySeverity, safetySeverities),
    safety_status: enumValue(filters.safetyStatus, safetyStatuses),
    decision_from: filters.decisionFrom || undefined,
    decision_to: filters.decisionTo || undefined,
    source_updated_from: filters.sourceUpdatedFrom || undefined,
    source_updated_to: filters.sourceUpdatedTo || undefined,
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
    sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
      (criterion) => `${criterion.field}:${criterion.direction}`,
    ),
    display_mode: filters.displayMode,
    analysis_view: filters.analysisView,
  };
}

export function hasRegulatorySearchFilter(filters: RegulatorySearchFilters): boolean {
  const query = savedRegulatoryQuery(filters);
  return Object.entries(query).some(
    ([key, value]) =>
      !["sort_by", "sort_direction", "sort", "display_mode", "analysis_view"].includes(key) && value !== undefined,
  );
}

export async function saveRegulatorySearch({
  name,
  filters,
  shared,
  monitor,
}: {
  name: string;
  filters: RegulatorySearchFilters;
  shared: boolean;
  monitor: boolean;
}): Promise<{ message: string }> {
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query_type: "regulatory_search",
        query: savedRegulatoryQuery(filters),
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
  return { message: monitor ? "监管检索已保存并启用监控" : "监管检索已保存" };
}

export const regulatoryKeys = {
  search: (filters: RegulatorySearchFilters, offset: number) =>
    ["intelligence", "regulatory", { ...filters, offset }] as const,
  detail: (eventId: string) => ["intelligence", "regulatory", "detail", eventId] as const,
  facetCatalog: () => ["intelligence", "regulatory", "facet-catalog"] as const,
};

export async function loadRegulatoryFacetCatalog(signal?: AbortSignal): Promise<RegulatoryFacetCatalog> {
  const result = await contractRequest(
    RegulatoryService.searchRegulatoryEventTimelineApiV1RegulatoryEventTimelineGet({
      limit: 1,
      offset: 0,
      sort: ["decision_date:desc"],
    }),
    signal,
  );
  return { as_of: result.as_of, facets: result.facets, warnings: result.warnings };
}

export async function searchRegulatoryEvents(
  filters: RegulatorySearchFilters,
  offset: number,
  signal?: AbortSignal,
): Promise<RegulatoryEventSearchResult> {
  return contractRequest(
    RegulatoryService.searchRegulatoryEventTimelineApiV1RegulatoryEventTimelineGet({
      q: filters.query.trim() || undefined,
      agency: filters.agency || undefined,
      jurisdiction: filters.jurisdiction || undefined,
      eventType: filters.eventType || undefined,
      status: filters.status || undefined,
      designationType: enumValue(filters.designationType, designationTypes),
      labelChangeType: enumValue(filters.labelChangeType, labelChangeTypes),
      hasBoxedWarning: boxedWarning(filters.boxedWarning),
      safetySignalType: enumValue(filters.safetySignalType, safetySignalTypes),
      safetySeverity: enumValue(filters.safetySeverity, safetySeverities),
      safetyStatus: enumValue(filters.safetyStatus, safetyStatuses),
      decisionFrom: filters.decisionFrom ? `${filters.decisionFrom}T00:00:00.000Z` : undefined,
      decisionTo: filters.decisionTo ? `${filters.decisionTo}T23:59:59.999Z` : undefined,
      sourceUpdatedFrom: filters.sourceUpdatedFrom ? `${filters.sourceUpdatedFrom}T00:00:00.000Z` : undefined,
      sourceUpdatedTo: filters.sourceUpdatedTo ? `${filters.sourceUpdatedTo}T23:59:59.999Z` : undefined,
      sort: effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).map(
        (criterion) => `${criterion.field}:${criterion.direction}`,
      ),
      limit: 100,
      offset,
    }),
    signal,
  );
}

export async function loadRegulatoryEventDetail(
  eventId: string,
  signal?: AbortSignal,
): Promise<RegulatoryEventSearchItemRead> {
  return contractRequest(
    RegulatoryService.getRegulatoryEventTimelineItemApiV1RegulatoryEventTimelineEventIdGet({ eventId }),
    signal,
  );
}
