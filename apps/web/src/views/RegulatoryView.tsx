import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ProfessionalQueryState } from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import { ApiError } from "../lib/api";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import {
  emptyRegulatorySearchFilters,
  hasRegulatorySearchFilter,
  loadRegulatoryEventDetail,
  type RegulatorySearchFilters,
  regulatoryKeys,
  regulatorySortFields,
  saveRegulatorySearch,
  searchRegulatoryEvents,
  validateRegulatorySearchFilters,
} from "../lib/contracts/regulatory";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import { useLocale } from "../lib/i18n";
import { RegulatoryLandscape } from "./regulatory/RegulatoryLandscape";
import { RegulatoryResultActions } from "./regulatory/RegulatoryResultActions";
import "../styles/regulatory-research.css";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { regulatoryText as t } from "../lib/i18n/regulatory";
import { publicCoverageNotice } from "../lib/publicWarnings";
import {
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../lib/regulatoryDisplay";
import { useFilterDraft } from "../lib/useFilterDraft";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";
import { regulatoryLabels } from "./regulatory/presentation";
import { RegulatoryComparison } from "./regulatory/RegulatoryComparison";
import { RegulatoryDetailDrawer } from "./regulatory/RegulatoryDetailDrawer";
import { RegulatoryFilterForm } from "./regulatory/RegulatoryFilterForm";
import { type RegulatorySaveFeedback, regulatorySaveFeedback } from "./regulatory/saveFeedback";
import { useRegulatoryColumns } from "./regulatory/useRegulatoryColumns";

const PAGE_SIZE = 100;

const appliedFilterLabels = {
  q: "关键词",
  agency: "监管机构",
  jurisdiction: "辖区",
  event_type: "事件类型",
  status: "事件状态",
  designation_type: "认定资格",
  label_change_type: "标签变更",
  has_boxed_warning: "黑框警告",
  safety_signal_type: "安全信号",
  safety_severity: "严重程度",
  safety_status: "信号状态",
  decision_from: "决定日期",
  decision_to: "决定日期",
  source_updated_from: "来源更新",
  source_updated_to: "来源更新",
} as const;
const appliedValueLabels = {
  event_type: eventTypeLabels,
  designation_type: designationLabels,
  label_change_type: labelChangeLabels,
  safety_signal_type: safetySignalLabels,
  safety_severity: severityLabels,
  safety_status: safetyStatusLabels,
};

export function RegulatoryView({
  initialFilters,
  initialOffset,
  selectedEventId,
  comparedEventIds,
  onSearchChange,
  onEventChange,
  onCompareChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  initialFilters: RegulatorySearchFilters;
  initialOffset: number;
  selectedEventId: string | null;
  comparedEventIds: string[];
  onSearchChange: (filters: RegulatorySearchFilters, offset: number) => void;
  onEventChange: (eventId: string | null) => void;
  onCompareChange: (eventIds: string[]) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  useLocale();
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveFeedback, setSaveFeedback] = useState<RegulatorySaveFeedback | null>(null);
  const saveMessage = regulatorySaveFeedback(saveFeedback);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const resultQueryKey = regulatoryKeys.search(initialFilters, initialOffset);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchRegulatoryEvents(initialFilters, initialOffset, signal),
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const detail = useQuery({
    queryKey: regulatoryKeys.detail(selectedEventId ?? ""),
    queryFn: ({ signal }) => loadRegulatoryEventDetail(selectedEventId ?? "", signal),
    enabled: Boolean(selectedEventId),
  });
  const comparisonQueries = useQueries({
    queries: comparedEventIds.map((eventId) => ({
      queryKey: regulatoryKeys.detail(eventId),
      queryFn: ({ signal }: { signal: AbortSignal }) => loadRegulatoryEventDetail(eventId, signal),
      staleTime: 60_000,
    })),
  });
  const save = useMutation({ mutationFn: saveRegulatorySearch });
  const openRegulatoryEntity = useCallback<DossierEntityOpener>(
    (entityType, entityId) => {
      switch (entityType) {
        case "drug":
          (onOpenDrug ?? onOpenEntity)(entityId);
          return;
        case "target":
          (onOpenTarget ?? onOpenEntity)(entityId);
          return;
        case "disease":
          (onOpenDisease ?? onOpenEntity)(entityId);
          return;
        case "organization":
          (onOpenOrganization ?? onOpenEntity)(entityId);
          return;
        default:
          onOpenEntity(entityId);
      }
    },
    [onOpenDisease, onOpenDrug, onOpenEntity, onOpenOrganization, onOpenTarget],
  );

  useEffect(() => {
    if (filters === initialFilters) setValidationError(null);
  }, [filters, initialFilters]);

  function updateFilter<K extends keyof RegulatorySearchFilters>(key: K, value: RegulatorySearchFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setValidationError(null);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const error = validateRegulatorySearchFilters(filters);
    if (error) {
      setValidationError(error);
      return;
    }
    onSearchChange({ ...filters, query: filters.query.trim() }, 0);
  }

  function clearFilters() {
    setFilters(emptyRegulatorySearchFilters);
    setValidationError(null);
    onSearchChange(emptyRegulatorySearchFilters, 0);
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "decision_date", direction: "desc" });
    if (
      !sort.every((criterion) => regulatorySortFields.includes(criterion.field as RegulatorySearchFilters["sortBy"]))
    ) {
      return;
    }
    const normalizedSort = sort as NonNullable<RegulatorySearchFilters["sort"]>;
    onSearchChange(
      {
        ...initialFilters,
        sortBy: normalizedSort[0].field,
        sortDirection: normalizedSort[0].direction,
        sort: normalizedSort,
      },
      0,
    );
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveFeedback(null);
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        filters: initialFilters,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveFeedback({ kind: "outcome", outcome });
    } catch (error) {
      setSaveFeedback({ kind: "error", reason: error instanceof Error ? error.message : null });
    }
  }

  const columns = useRegulatoryColumns(onEventChange, openRegulatoryEntity);

  const resultDenied = result.error instanceof ApiError && [401, 403].includes(result.error.status);
  const data = resultDenied ? undefined : result.data;
  const detailDenied = detail.error instanceof ApiError && [401, 403].includes(detail.error.status);
  const detailMismatch = !detailDenied && detail.data && detail.data.id !== selectedEventId;
  const detailData = detailDenied || detailMismatch ? undefined : detail.data;
  const detailError = detailMismatch
    ? new Error(t("监管详情与请求标识不一致"))
    : detail.error instanceof Error
      ? detail.error
      : null;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const agencies = facetOptions(data?.facets, "agency", filters.agency);
  const jurisdictions = facetOptions(data?.facets, "jurisdiction", filters.jurisdiction);
  const eventTypes = facetOptions(data?.facets, "event_type", filters.eventType);
  const statuses = facetOptions(data?.facets, "status", filters.status);
  const hasFilters = hasRegulatorySearchFilter(initialFilters) || hasRegulatorySearchFilter(filters);
  const comparedEvents = comparisonQueries.flatMap((query, index) =>
    query.data &&
    query.data.id === comparedEventIds[index] &&
    !(query.error instanceof ApiError && [401, 403].includes(query.error.status))
      ? [query.data]
      : [],
  );
  const comparisonLoading = comparisonQueries.some((query) => query.isFetching);
  const comparisonError =
    comparisonQueries.find((query) => query.error)?.error ??
    (comparisonQueries.some((query, index) => query.data && query.data.id !== comparedEventIds[index])
      ? new Error(t("对比记录与请求标识不一致"))
      : null);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <>
      <section className="data-section regulatory-section">
        <div className="explorer-intro">
          <p>{t("追踪监管决定、标签与安全信号，核对适用范围和原始证据。")}</p>
        </div>

        <RegulatoryFilterForm
          filters={filters}
          facets={data?.facets}
          agencies={agencies}
          jurisdictions={jurisdictions}
          eventTypes={eventTypes}
          statuses={statuses}
          updateFilter={updateFilter}
          submit={submit}
          clearFilters={clearFilters}
          querying={result.isFetching}
          clearable={hasFilters}
          validationError={validationError ? professionalValidationText(validationError) : ""}
        />

        <AppliedFiltersBar
          filters={data?.applied_filters}
          labels={Object.fromEntries(Object.entries(appliedFilterLabels).map(([key, caption]) => [key, t(caption)]))}
          valueLabels={Object.fromEntries(
            Object.entries(appliedValueLabels).map(([key, labels]) => [key, regulatoryLabels(labels)]),
          )}
          onClear={clearFilters}
        />

        {comparedEventIds.length ? (
          <RegulatoryComparison
            events={comparedEvents}
            loading={comparisonLoading}
            error={comparisonError instanceof Error ? comparisonError : null}
            selectedCount={comparedEventIds.length}
            onRemove={(eventId) => onCompareChange(comparedEventIds.filter((id) => id !== eventId))}
            onClear={() => onCompareChange([])}
            onOpen={(eventId) => onEventChange(eventId)}
            onRetry={() => {
              for (const query of comparisonQueries) void query.refetch();
            }}
          />
        ) : null}

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel={t("正在查询监管事件")}
          refreshingLabel={t("正在刷新监管事件")}
          fallbackError={t("监管事件加载失败")}
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <RegulatoryResultActions
                data={data}
                filters={initialFilters}
                refreshing={result.isFetching}
                saveable={hasRegulatorySearchFilter(initialFilters)}
                onRefresh={retryResult}
                onDisplayMode={(displayMode) => onSearchChange({ ...initialFilters, displayMode }, 0)}
                onSave={() => {
                  setSaveName(initialFilters.query.trim() || t("监管安全监控"));
                  setSaveFeedback(null);
                  save.reset();
                  setSaveOpen(true);
                }}
              />
              {initialFilters.displayMode === "landscape" ? (
                <RegulatoryLandscape
                  landscape={data.landscape}
                  view={initialFilters.analysisView}
                  onViewChange={(analysisView) => onSearchChange({ ...initialFilters, analysisView }, 0)}
                  onFilter={(field, value) =>
                    onSearchChange(
                      field === "event_type"
                        ? { ...initialFilters, eventType: value }
                        : { ...initialFilters, agency: value },
                      0,
                    )
                  }
                />
              ) : data.items.length ? (
                <VirtualDataTable
                  ariaLabel={t("监管事件结果")}
                  columns={columns}
                  data={data.items}
                  getRowId={(item) => item.id}
                  preferenceKey="regulatory-events"
                  totalRows={data.total}
                  sorting={sorting}
                  onSortingChange={changeSorting}
                  sortingScope="all"
                  defaultSorting={[{ id: "decision_date", desc: true }]}
                  toolbarActions={<DomainExportControl dataset="regulatory" totalRows={data.total} />}
                  rowSelection={{
                    selectedRowIds: comparedEventIds,
                    onChange: onCompareChange,
                    getRowLabel: (item) => t("对比 {title}", { title: item.title }),
                    label: t("选择事件对比，最多 4 项"),
                    maxSelectedRows: 4,
                    allowSelectAll: false,
                  }}
                />
              ) : (
                <EmptyQueryResult
                  domain={t("监管事件")}
                  filtered={Boolean(data.applied_filters?.length)}
                  onClear={clearFilters}
                />
              )}
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange(initialFilters, offset)}
                ariaLabel={t("监管事件结果分页")}
              />
            </div>
          ) : null}
        </ProfessionalQueryState>
        {saveMessage && !saveOpen ? (
          <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
            {saveMessage}
          </p>
        ) : null}
        <SavedSearchDialog
          open={saveOpen}
          domainLabel={t("监管")}
          name={saveName}
          shared={saveShared}
          monitor={saveMonitor}
          pending={save.isPending}
          error={save.isError ? saveMessage : ""}
          onNameChange={setSaveName}
          onSharedChange={setSaveShared}
          onMonitorChange={setSaveMonitor}
          onClose={() => setSaveOpen(false)}
          onSubmit={(event) => void submitSavedSearch(event)}
        />
      </section>

      {selectedEventId ? (
        <RegulatoryDetailDrawer
          data={detailData}
          loading={detail.isFetching}
          error={detailError}
          onRetry={() => void detail.refetch()}
          onClose={() => onEventChange(null)}
          onOpenEntity={onOpenEntity}
          onOpenTypedEntity={openRegulatoryEntity}
          onOpenProvenance={setProvenanceSelection}
        />
      ) : null}
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}
