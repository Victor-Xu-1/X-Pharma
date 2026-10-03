import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { BookmarkPlus, Columns3, ExternalLink, FileText, Search, SlidersHorizontal, X } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import {
  ErrorState,
  formatDate,
  ProfessionalQueryState,
  QueryRefreshButton,
  Spinner,
  StatusBadge,
} from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { DomainLandscape } from "../components/DomainLandscape";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  emptyRegulatorySearchFilters,
  hasRegulatorySearchFilter,
  loadRegulatoryEventDetail,
  type RegulatorySearchFilters,
  regulatoryKeys,
  saveRegulatorySearch,
  searchRegulatoryEvents,
  validateRegulatorySearchFilters,
} from "../lib/contracts/regulatory";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import type { RegulatoryEventSearchItemRead } from "../lib/generated";
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
import { useModalFocus } from "../lib/useModalFocus";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";

const PAGE_SIZE = 100;
const regulatorySortFields: RegulatorySearchFilters["sortBy"][] = [
  "decision_date",
  "title",
  "agency",
  "jurisdiction",
  "event_type",
  "status",
  "subject",
  "source_updated_at",
];

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

function detailsSummary(details: Record<string, unknown>) {
  const entries = Object.entries(details);
  return entries.length
    ? entries
        .slice(0, 2)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(" · ")
    : "未披露补充信息";
}

function displayValue(value: string | null | undefined, labels?: Record<string, string>) {
  if (!value) return "未披露";
  return labels?.[value] ?? value;
}

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
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
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
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        filters: initialFilters,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome.message);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "监管检索保存失败");
    }
  }

  const columns = useMemo<ColumnDef<RegulatoryEventSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "title",
        header: "监管事件",
        size: 280,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onEventChange(row.original.id)}>
            <strong>{row.original.title}</strong>
            <small>{row.original.event_identifier}</small>
          </button>
        ),
      },
      {
        accessorKey: "decision_date",
        header: "决定日期",
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "agency",
        accessorFn: (row) => row.agency,
        header: "机构 / 辖区",
        size: 120,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{row.original.agency}</strong>
            <small>{row.original.jurisdiction}</small>
          </span>
        ),
      },
      {
        accessorKey: "event_type",
        header: "事件类型",
        size: 110,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "--");
          return <StatusBadge value={eventTypeLabels[value] ?? value} />;
        },
      },
      {
        id: "designation",
        header: "认定 / 标签",
        size: 155,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{displayValue(row.original.designation_type, designationLabels)}</strong>
            <small>
              {displayValue(row.original.label_change_type, labelChangeLabels)}
              {row.original.label_version ? ` · ${row.original.label_version}` : ""}
            </small>
          </span>
        ),
      },
      {
        id: "safety",
        header: "安全信号",
        size: 175,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{displayValue(row.original.safety_term)}</strong>
            <small>
              {displayValue(row.original.safety_severity, severityLabels)} ·{" "}
              {displayValue(row.original.safety_status, safetyStatusLabels)}
            </small>
          </span>
        ),
      },
      {
        id: "subject",
        accessorFn: (row) => row.subject_entity.name,
        header: "药物 / 产品",
        size: 145,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            onClick={() =>
              openRegulatoryEntity(row.original.subject_entity.entity_type, row.original.subject_entity.id)
            }
          >
            <strong>{row.original.subject_entity.name}</strong>
            <small>{row.original.application_number ?? "申请号未披露"}</small>
          </button>
        ),
      },
      {
        id: "indication",
        header: "适应症 / 人群",
        size: 175,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            {row.original.indication_entity ? (
              <button
                className="table-link-button"
                type="button"
                onClick={() =>
                  openRegulatoryEntity(
                    row.original.indication_entity?.entity_type ?? "disease",
                    row.original.indication_entity?.id ?? "",
                  )
                }
              >
                {row.original.indication_entity.name}
              </button>
            ) : (
              <strong>未关联适应症</strong>
            )}
            <small>{row.original.approved_population ?? row.original.affected_population ?? "人群未披露"}</small>
          </span>
        ),
      },
      {
        id: "open",
        header: "档案",
        size: 55,
        enableSorting: false,
        cell: ({ row }) => (
          <button
            className="icon-button"
            type="button"
            title={`打开 ${row.original.subject_entity.name} 档案`}
            aria-label={`打开 ${row.original.subject_entity.name} 档案`}
            onClick={() =>
              openRegulatoryEntity(row.original.subject_entity.entity_type, row.original.subject_entity.id)
            }
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onEventChange, openRegulatoryEntity],
  );

  const data = result.data;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const agencies = facetOptions(data?.facets, "agency", filters.agency);
  const jurisdictions = facetOptions(data?.facets, "jurisdiction", filters.jurisdiction);
  const eventTypes = facetOptions(data?.facets, "event_type", filters.eventType);
  const statuses = facetOptions(data?.facets, "status", filters.status);
  const hasFilters = Object.values(initialFilters).some(Boolean);
  const comparedEvents = comparisonQueries.flatMap((query) => (query.data ? [query.data] : []));
  const comparisonLoading = comparisonQueries.some((query) => query.isFetching);
  const comparisonError = comparisonQueries.find((query) => query.error)?.error;

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <>
      <section className="data-section regulatory-section">
        <div className="explorer-intro">
          <p>统一比较申报、批准、认定资格、标签版本和安全信号，追踪适用人群、风险措施及来源更新时间。</p>
        </div>

        <form className="domain-filter-bar regulatory-filter-bar" onSubmit={submit} aria-label="监管事件筛选">
          <label className="domain-query-field">
            <span>关键词</span>
            <span className="input-with-icon">
              <Search size={16} />
              <input
                value={filters.query}
                onChange={(event) => updateFilter("query", event.target.value)}
                placeholder="药物、适应症、申请号、标签或安全术语"
                maxLength={500}
              />
            </span>
          </label>
          <label>
            <span>监管机构</span>
            <select value={filters.agency} onChange={(event) => updateFilter("agency", event.target.value)}>
              <option value="">全部</option>
              {agencies.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.agency?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>辖区</span>
            <select value={filters.jurisdiction} onChange={(event) => updateFilter("jurisdiction", event.target.value)}>
              <option value="">全部</option>
              {jurisdictions.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.jurisdiction?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>事件类型</span>
            <select value={filters.eventType} onChange={(event) => updateFilter("eventType", event.target.value)}>
              <option value="">全部</option>
              {eventTypes.map((value) => (
                <option value={value} key={value}>
                  {eventTypeLabels[value] ?? value} ({data?.facets?.event_type?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>认定资格</span>
            <select
              value={filters.designationType}
              onChange={(event) => updateFilter("designationType", event.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(designationLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label} ({data?.facets?.designation_type?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>

          <details className="advanced-filter-panel">
            <summary>
              <SlidersHorizontal size={16} />
              更多监管与安全条件
            </summary>
            <div className="advanced-filter-grid regulatory-advanced-filter-grid">
              <label>
                <span>事件状态</span>
                <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
                  <option value="">全部</option>
                  {statuses.map((value) => (
                    <option value={value} key={value}>
                      {value} ({data?.facets?.status?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>标签变更</span>
                <select
                  value={filters.labelChangeType}
                  onChange={(event) => updateFilter("labelChangeType", event.target.value)}
                >
                  <option value="">全部</option>
                  {Object.entries(labelChangeLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label} ({data?.facets?.label_change_type?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>黑框警告</span>
                <select
                  aria-label="黑框警告"
                  value={filters.boxedWarning}
                  onChange={(event) => updateFilter("boxedWarning", event.target.value)}
                >
                  <option value="">全部</option>
                  <option value="true">有 ({data?.facets?.has_boxed_warning?.true ?? 0})</option>
                  <option value="false">无 ({data?.facets?.has_boxed_warning?.false ?? 0})</option>
                </select>
              </label>
              <label>
                <span>安全信号</span>
                <select
                  aria-label="安全信号"
                  value={filters.safetySignalType}
                  onChange={(event) => updateFilter("safetySignalType", event.target.value)}
                >
                  <option value="">全部</option>
                  {Object.entries(safetySignalLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label} ({data?.facets?.safety_signal_type?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>严重程度</span>
                <select
                  value={filters.safetySeverity}
                  onChange={(event) => updateFilter("safetySeverity", event.target.value)}
                >
                  <option value="">全部</option>
                  {Object.entries(severityLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label} ({data?.facets?.safety_severity?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>信号状态</span>
                <select
                  value={filters.safetyStatus}
                  onChange={(event) => updateFilter("safetyStatus", event.target.value)}
                >
                  <option value="">全部</option>
                  {Object.entries(safetyStatusLabels).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label} ({data?.facets?.safety_status?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <DateRangeFields
                label="决定日期"
                from={filters.decisionFrom}
                to={filters.decisionTo}
                onFrom={(value) => updateFilter("decisionFrom", value)}
                onTo={(value) => updateFilter("decisionTo", value)}
              />
              <DateRangeFields
                label="来源更新"
                from={filters.sourceUpdatedFrom}
                to={filters.sourceUpdatedTo}
                onFrom={(value) => updateFilter("sourceUpdatedFrom", value)}
                onTo={(value) => updateFilter("sourceUpdatedTo", value)}
              />
            </div>
          </details>

          {validationError ? (
            <p className="form-error regulatory-filter-error" role="alert">
              {validationError}
            </p>
          ) : null}
          <div className="domain-filter-actions regulatory-filter-actions">
            <button className="primary-button" type="submit" disabled={result.isFetching}>
              <Search size={16} />
              查询
            </button>
            <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
              清除
            </button>
          </div>
        </form>

        <AppliedFiltersBar
          filters={data?.applied_filters}
          labels={appliedFilterLabels}
          valueLabels={appliedValueLabels}
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
          />
        ) : null}

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel="正在查询监管事件"
          fallbackError="监管事件加载失败"
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <div className="pipeline-result-toolbar">
                <QueryResultSummary
                  total={data.total}
                  offset={data.offset}
                  count={data.items.length}
                  unit="项监管事件"
                  queriedAt={data.as_of}
                  note="最多对比 4 项"
                />
                <div className="pipeline-result-actions">
                  <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                  <fieldset className="segmented-control">
                    <legend className="sr-only">结果展示方式</legend>
                    <button
                      type="button"
                      aria-pressed={initialFilters.displayMode === "list"}
                      onClick={() => onSearchChange({ ...initialFilters, displayMode: "list" }, 0)}
                    >
                      列表
                    </button>
                    <button
                      type="button"
                      aria-pressed={initialFilters.displayMode === "landscape"}
                      onClick={() => onSearchChange({ ...initialFilters, displayMode: "landscape" }, 0)}
                    >
                      统计
                    </button>
                  </fieldset>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!hasRegulatorySearchFilter(initialFilters)}
                    title={
                      hasRegulatorySearchFilter(initialFilters) ? "保存或订阅当前监管查询" : "至少应用一个查询条件"
                    }
                    onClick={() => {
                      setSaveName(initialFilters.query.trim() || "监管安全监控");
                      setSaveMessage("");
                      setSaveOpen(true);
                    }}
                  >
                    <BookmarkPlus size={15} />
                    保存/订阅
                  </button>
                </div>
              </div>
              {initialFilters.displayMode === "landscape" ? (
                <DomainLandscape<"event_type" | "agency">
                  domainId="regulatory"
                  ariaLabel="监管统计分析"
                  total={data.landscape.total_events}
                  totalUnit="项监管事件"
                  unitLabel="事件数"
                  sections={[
                    {
                      id: "event-type",
                      title: "事件类型",
                      detail: "按事件类型统计完整命中集",
                      buckets: data.landscape.event_type ?? [],
                      filterField: "event_type",
                    },
                    {
                      id: "agency",
                      title: "监管机构",
                      detail: "按监管机构统计完整命中集",
                      buckets: data.landscape.agency ?? [],
                      filterField: "agency",
                    },
                    {
                      id: "decision-year",
                      title: "决定年份",
                      detail: "按决定年份统计完整命中集",
                      buckets: data.landscape.decision_year ?? [],
                      filterField: null,
                    },
                  ]}
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
                  ariaLabel="监管事件结果"
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
                    getRowLabel: (item) => `对比 ${item.title}`,
                    label: "选择事件进行对比",
                    maxSelectedRows: 4,
                    allowSelectAll: false,
                  }}
                />
              ) : (
                <EmptyQueryResult
                  domain="监管事件"
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
                ariaLabel="监管事件结果分页"
              />
            </div>
          ) : null}
        </ProfessionalQueryState>
        {saveMessage ? (
          <p className="inline-feedback" role="status">
            {saveMessage}
          </p>
        ) : null}
        <SavedSearchDialog
          open={saveOpen}
          domainLabel="监管"
          name={saveName}
          shared={saveShared}
          monitor={saveMonitor}
          pending={save.isPending}
          onNameChange={setSaveName}
          onSharedChange={setSaveShared}
          onMonitorChange={setSaveMonitor}
          onClose={() => setSaveOpen(false)}
          onSubmit={(event) => void submitSavedSearch(event)}
        />
      </section>

      {selectedEventId ? (
        <RegulatoryDetailDrawer
          eventId={selectedEventId}
          data={detail.data}
          loading={detail.isFetching}
          error={detail.error instanceof Error ? detail.error : null}
          onRetry={() => void detail.refetch()}
          onClose={() => onEventChange(null)}
          onOpenEntity={onOpenEntity}
          onOpenTypedEntity={openRegulatoryEntity}
        />
      ) : null}
    </>
  );
}

function DateRangeFields({
  label,
  from,
  to,
  onFrom,
  onTo,
}: {
  label: string;
  from: string;
  to: string;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
}) {
  return (
    <fieldset className="filter-range-field">
      <legend>{label}</legend>
      <label>
        <span>起</span>
        <input type="date" value={from} onChange={(event) => onFrom(event.target.value)} />
      </label>
      <label>
        <span>止</span>
        <input type="date" value={to} onChange={(event) => onTo(event.target.value)} />
      </label>
    </fieldset>
  );
}

function RegulatoryComparison({
  events,
  loading,
  error,
  selectedCount,
  onRemove,
  onClear,
  onOpen,
}: {
  events: RegulatoryEventSearchItemRead[];
  loading: boolean;
  error: Error | null;
  selectedCount: number;
  onRemove: (eventId: string) => void;
  onClear: () => void;
  onOpen: (eventId: string) => void;
}) {
  const metrics: Array<[string, (event: RegulatoryEventSearchItemRead) => string]> = [
    ["监管机构 / 辖区", (event) => `${event.agency} / ${event.jurisdiction}`],
    [
      "事件 / 日期",
      (event) => `${eventTypeLabels[event.event_type] ?? event.event_type} / ${formatDate(event.decision_date ?? "")}`,
    ],
    ["认定资格", (event) => displayValue(event.designation_type, designationLabels)],
    [
      "标签",
      (event) => `${displayValue(event.label_change_type, labelChangeLabels)} / ${event.label_version ?? "版本未披露"}`,
    ],
    ["批准人群", (event) => event.approved_population ?? "未披露"],
    ["生物标志物", (event) => event.biomarker ?? "未披露"],
    ["给药信息", (event) => [event.route_of_administration, event.dosage_form].filter(Boolean).join(" / ") || "未披露"],
    ["黑框警告", (event) => (event.has_boxed_warning === null ? "未披露" : event.has_boxed_warning ? "有" : "无")],
    [
      "安全信号",
      (event) => `${displayValue(event.safety_term)} / ${displayValue(event.safety_severity, severityLabels)}`,
    ],
    ["信号状态", (event) => displayValue(event.safety_status, safetyStatusLabels)],
    ["风险措施", (event) => event.risk_actions.join("；") || "未披露"],
    ["来源更新", (event) => formatDate(event.source_updated_at ?? "", true)],
  ];

  return (
    <section className="regulatory-comparison" aria-label="监管事件对比">
      <header>
        <div>
          <Columns3 size={17} />
          <strong>监管事件对比</strong>
          <span>{selectedCount}/4</span>
        </div>
        <button className="secondary-button" type="button" onClick={onClear}>
          清空对比
        </button>
      </header>
      {loading && !events.length ? <Spinner label="正在加载对比事件" /> : null}
      {error ? (
        <p className="form-error" role="alert">
          {error.message || "对比事件加载失败"}
        </p>
      ) : null}
      {events.length ? (
        <div className="regulatory-comparison-scroll">
          <table className="comparison-table regulatory-comparison-table" aria-label="监管事件对比">
            <thead>
              <tr>
                <th>比较维度</th>
                {events.map((event) => (
                  <th key={event.id}>
                    <button type="button" onClick={() => onOpen(event.id)}>
                      {event.subject_entity.name}
                    </button>
                    <small>{event.event_identifier}</small>
                    <button
                      className="icon-button"
                      type="button"
                      aria-label={`移除 ${event.title}`}
                      title="移除对比"
                      onClick={() => onRemove(event.id)}
                    >
                      <X size={14} />
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, render]) => (
                <tr key={label}>
                  <th>{label}</th>
                  {events.map((event) => (
                    <td key={event.id}>{render(event)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function RegulatoryDetailDrawer({
  eventId,
  data,
  loading,
  error,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  eventId: string;
  data: RegulatoryEventSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
}) {
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);

  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label="关闭监管事件详情" onClick={onClose} />
      <aside
        ref={dialogRef}
        className="detail-drawer regulatory-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="regulatory-event-title"
        tabIndex={-1}
      >
        <header className="deal-detail-header">
          <div>
            <span>{data ? `${data.agency} · ${data.jurisdiction} · ${data.event_identifier}` : eventId}</span>
            <h2 id="regulatory-event-title">{data?.title ?? "监管事件详情"}</h2>
            {data ? (
              <div className="trial-detail-status">
                <StatusBadge value={eventTypeLabels[data.event_type] ?? data.event_type} />
                <span>{formatDate(data.decision_date ?? "")}</span>
                <span>{data.status ?? "状态未披露"}</span>
              </div>
            ) : null}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭监管事件详情"
            title="关闭"
            data-modal-autofocus="true"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {loading ? (
          <Spinner label="正在加载监管事件详情" />
        ) : error ? (
          <ErrorState message={error.message || "监管事件详情加载失败"} retry={onRetry} />
        ) : data ? (
          <div className="drawer-content deal-detail-content regulatory-detail-content">
            <section>
              <h3>事件口径</h3>
              <dl className="trial-detail-grid">
                <DetailValue term="监管机构" value={`${data.agency} / ${data.jurisdiction}`} />
                <DetailValue term="事件类型" value={eventTypeLabels[data.event_type] ?? data.event_type} />
                <DetailValue term="申请号" value={data.application_number} />
                <DetailValue term="决定日期" value={formatDate(data.decision_date ?? "")} />
                <DetailValue term="认定资格" value={displayValue(data.designation_type, designationLabels)} />
                <DetailValue term="来源更新" value={formatDate(data.source_updated_at ?? "", true)} />
              </dl>
            </section>
            <section>
              <h3>标签与适用范围</h3>
              <dl className="trial-detail-grid">
                <DetailValue term="标签变更" value={displayValue(data.label_change_type, labelChangeLabels)} />
                <DetailValue term="标签版本" value={data.label_version} />
                <DetailValue term="生效日期" value={formatDate(data.label_effective_at ?? "")} />
                <DetailValue term="批准人群" value={data.approved_population} />
                <DetailValue term="治疗线次" value={data.line_of_therapy} />
                <DetailValue term="生物标志物" value={data.biomarker} />
                <DetailValue term="给药途径" value={data.route_of_administration} />
                <DetailValue term="剂型" value={data.dosage_form} />
                <DetailValue
                  term="黑框警告"
                  value={data.has_boxed_warning === null ? "未披露" : data.has_boxed_warning ? "有" : "无"}
                />
              </dl>
            </section>
            <section>
              <h3>安全信号与风险措施</h3>
              <dl className="trial-detail-grid">
                <DetailValue term="信号类型" value={displayValue(data.safety_signal_type, safetySignalLabels)} />
                <DetailValue term="安全术语" value={data.safety_term} />
                <DetailValue term="严重程度" value={displayValue(data.safety_severity, severityLabels)} />
                <DetailValue term="信号状态" value={displayValue(data.safety_status, safetyStatusLabels)} />
                <DetailValue term="影响人群" value={data.affected_population} />
                <DetailValue term="识别日期" value={formatDate(data.safety_identified_at ?? "")} />
                <DetailValue term="确认日期" value={formatDate(data.safety_confirmed_at ?? "")} />
                <DetailValue term="解决日期" value={formatDate(data.safety_resolved_at ?? "")} />
              </dl>
              <p className="regulatory-risk-actions">
                {data.risk_actions.length ? data.risk_actions.join("；") : "风险措施未披露"}
              </p>
            </section>
            <section>
              <h3>关联实体</h3>
              <div className="deal-detail-list">
                <button
                  type="button"
                  onClick={() => {
                    if (onOpenTypedEntity) {
                      onOpenTypedEntity(data.subject_entity.entity_type, data.subject_entity.id);
                      return;
                    }
                    onOpenEntity(data.subject_entity.id);
                  }}
                >
                  <strong>{data.subject_entity.name}</strong>
                  <span>药物 / 产品</span>
                </button>
                {data.indication_entity ? (
                  <button
                    type="button"
                    onClick={() => {
                      const entityId = data.indication_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.indication_entity?.entity_type ?? "disease", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.indication_entity.name}</strong>
                    <span>适应症</span>
                  </button>
                ) : (
                  <span>适应症未关联</span>
                )}
                {data.organization_entity ? (
                  <button
                    type="button"
                    aria-label={`打开 ${data.organization_entity.name} 档案`}
                    onClick={() => {
                      const entityId = data.organization_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.organization_entity?.entity_type ?? "organization", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.organization_entity.name}</strong>
                    <span>申办方</span>
                  </button>
                ) : (
                  <span>申办方未关联</span>
                )}
              </div>
            </section>
            <section>
              <h3>补充信息与来源</h3>
              <p>{detailsSummary(data.details)}</p>
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? `来源文档 ${data.source_document_id}` : "来源文档未关联"}
              </p>
            </section>
          </div>
        ) : null}
      </aside>
    </div>
  );
}

function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || "未披露"}</dd>
    </div>
  );
}
