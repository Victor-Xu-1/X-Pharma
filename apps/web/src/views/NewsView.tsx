import { useMutation, useQuery } from "@tanstack/react-query";
import { BookmarkPlus, CalendarDays, ExternalLink, FileText, List, Search, X } from "lucide-react";
import { type FormEvent, useCallback, useMemo, useState } from "react";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import {
  EmptyState,
  ErrorState,
  formatDate,
  ProfessionalQueryState,
  QueryRefreshButton,
  Spinner,
  StatusBadge,
} from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { DomainLandscape } from "../components/DomainLandscape";
import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  hasNewsSearchFilter,
  loadNewsEventDetail,
  type NewsSearchFilters,
  newsKeys,
  newsSortFields,
  saveNewsSearch,
  searchNewsEvents,
} from "../lib/contracts/news";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import type { NewsEventSearchItemRead } from "../lib/generated";
import { newsEntityTypes, newsEventTypeLabels } from "../lib/newsDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { useModalFocus } from "../lib/useModalFocus";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";

const PAGE_SIZE = 100;
const defaultNewsSorting: SortingState = [{ id: "published_at", desc: true }];

const researchEventTypes = new Set(["publication", "conference_abstract", "poster", "presentation"]);
const appliedFilterLabels = {
  entity_id: "关联实体",
  q: "关键词",
  event_type: "事件类型",
  publisher: "发布机构",
  language: "语言",
  venue: "会议或期刊",
  published_from: "发布起始",
  published_to: "发布截止",
  content_scope: "内容范围",
} as const;
const appliedValueLabels = {
  event_type: newsEventTypeLabels,
  content_scope: { research: "研究发布" },
};

function detailsSummary(details: Record<string, unknown>) {
  const entries = Object.entries(details);
  if (!entries.length) return "未披露";
  return entries
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
    .join(" · ");
}

function NewsResearchTimeline({
  items,
  onOpenTypedEntity,
  onOpenDetail,
  onOpenProvenance,
}: {
  items: NewsEventSearchItemRead[];
  onOpenTypedEntity: DossierEntityOpener;
  onOpenDetail: (eventId: string) => void;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  return (
    <section className="news-research-timeline" aria-label="研究发布时间线">
      {items.map((item) => (
        <article key={item.id}>
          <div className="news-timeline-date">
            <time dateTime={item.published_at ?? undefined}>{formatDate(item.published_at ?? "")}</time>
            <StatusBadge value={newsEventTypeLabels[item.event_type] ?? item.event_type} />
          </div>
          <div className="news-timeline-content">
            <header>
              <h3>
                <button type="button" onClick={() => onOpenDetail(item.id)}>
                  {item.title}
                </button>
              </h3>
              {item.venue ? <span>{item.venue}</span> : null}
            </header>
            {item.summary ? <p>{item.summary}</p> : null}
            <div className="news-timeline-links">
              {item.publisher_entity ? (
                <button
                  type="button"
                  onClick={() =>
                    onOpenTypedEntity(
                      item.publisher_entity?.entity_type ?? "organization",
                      item.publisher_entity?.id ?? "",
                    )
                  }
                >
                  {item.publisher_entity.name}
                </button>
              ) : null}
              {item.related_entities.map((entity) => (
                <button type="button" key={entity.id} onClick={() => onOpenTypedEntity(entity.entity_type, entity.id)}>
                  {entity.name}
                </button>
              ))}
            </div>
            <div className="news-timeline-actions">
              {item.canonical_url ? (
                <a href={item.canonical_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} />
                  原始发布页
                </a>
              ) : null}
              <ProvenanceButton
                selection={{ resourceType: "news_event", resourceId: item.id, label: item.title }}
                onOpen={onOpenProvenance}
              />
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

export function NewsView({
  initialFilters,
  initialOffset,
  selectedNewsEventId,
  onSearchChange,
  onNewsEventChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  initialFilters: NewsSearchFilters;
  initialOffset: number;
  selectedNewsEventId: string | null;
  onSearchChange: (filters: NewsSearchFilters, offset: number) => void;
  onNewsEventChange: (eventId: string | null) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const resultQueryKey = newsKeys.search(initialFilters, initialOffset);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchNewsEvents(initialFilters, initialOffset, signal),
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const detail = useQuery({
    queryKey: newsKeys.detail(selectedNewsEventId ?? ""),
    queryFn: ({ signal }) => loadNewsEventDetail(selectedNewsEventId ?? "", signal),
    enabled: Boolean(selectedNewsEventId),
  });
  const save = useMutation({ mutationFn: saveNewsSearch });
  const openNewsEntity = useCallback<DossierEntityOpener>(
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

  function updateFilter<K extends keyof NewsSearchFilters>(key: K, value: NewsSearchFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearchChange({ ...filters, query: filters.query.trim() }, 0);
  }

  function clearFilters() {
    const cleared: NewsSearchFilters = {
      query: "",
      entityId: "",
      eventType: "",
      publisher: "",
      language: "",
      venue: "",
      publishedFrom: "",
      publishedTo: "",
      contentScope: "",
      displayMode: "list",
      analysisView: "chart",
      sortBy: "published_at",
      sortDirection: "desc",
    };
    setFilters(cleared);
    onSearchChange(cleared, 0);
  }

  function changeDisplayMode(displayMode: "list" | "timeline" | "landscape") {
    const next: NewsSearchFilters = {
      ...filters,
      eventType:
        displayMode === "timeline" && filters.eventType && !researchEventTypes.has(filters.eventType)
          ? ""
          : filters.eventType,
      contentScope: displayMode === "timeline" ? "research" : "",
      displayMode,
    };
    setFilters(next);
    onSearchChange(next, 0);
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "published_at", direction: "desc" });
    if (!sort.every((criterion) => newsSortFields.includes(criterion.field as NewsSearchFilters["sortBy"]))) return;
    const normalizedSort = sort as NonNullable<NewsSearchFilters["sort"]>;
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
      setSaveMessage(error instanceof Error ? error.message : "新闻与会议检索保存失败");
    }
  }

  const columns = useMemo<ColumnDef<NewsEventSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "published_at",
        header: "发布日期",
        size: 108,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "title",
        header: "标题与摘要",
        size: 360,
        cell: ({ row }) => (
          <button
            className="entity-name-button domain-primary-cell"
            type="button"
            aria-label={`打开新闻事件详情：${row.original.title}`}
            onClick={() => onNewsEventChange(row.original.id)}
          >
            <strong>{row.original.title}</strong>
            <small>{row.original.summary ?? row.original.event_identifier}</small>
          </button>
        ),
      },
      {
        accessorKey: "event_type",
        header: "类型",
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "other");
          return <StatusBadge value={newsEventTypeLabels[value] ?? value} />;
        },
      },
      {
        id: "publisher",
        accessorFn: (row) => row.publisher_entity?.name ?? null,
        header: "发布方",
        size: 150,
        cell: ({ row }) =>
          row.original.publisher_entity ? (
            <button
              className="table-link-button"
              type="button"
              onClick={() =>
                openNewsEntity(
                  row.original.publisher_entity?.entity_type ?? "organization",
                  row.original.publisher_entity?.id ?? "",
                )
              }
            >
              {row.original.publisher_entity.name}
            </button>
          ) : (
            "--"
          ),
      },
      {
        id: "entities",
        header: "关联对象",
        size: 220,
        enableSorting: false,
        cell: ({ row }) =>
          row.original.related_entities.length ? (
            <span className="linked-entity-list">
              {row.original.related_entities.slice(0, 3).map((entity) => (
                <button
                  className="table-link-button"
                  type="button"
                  key={entity.id}
                  onClick={() => openNewsEntity(entity.entity_type, entity.id)}
                >
                  {entity.name}
                </button>
              ))}
              {row.original.related_entities.length > 3 ? (
                <small>+{row.original.related_entities.length - 3}</small>
              ) : null}
            </span>
          ) : (
            "--"
          ),
      },
      {
        accessorKey: "venue",
        header: "会议 / 语言",
        size: 125,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{row.original.venue ?? "--"}</strong>
            <small>{row.original.language ?? "--"}</small>
          </span>
        ),
      },
      {
        id: "source",
        header: "来源",
        size: 78,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-action-group">
            {row.original.canonical_url ? (
              <a
                className="icon-button"
                href={row.original.canonical_url}
                target="_blank"
                rel="noreferrer"
                title="打开原始发布页"
                aria-label={`打开 ${row.original.title} 原始发布页`}
              >
                <ExternalLink size={16} />
              </a>
            ) : null}
            <ProvenanceButton
              selection={{ resourceType: "news_event", resourceId: row.original.id, label: row.original.title }}
              onOpen={setProvenanceSelection}
            />
          </span>
        ),
      },
    ],
    [onNewsEventChange, openNewsEntity],
  );

  const data = result.data;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const eventTypes = facetOptions(data?.facets, "event_type", filters.eventType);
  const publishers = facetOptions(data?.facets, "publisher", filters.publisher);
  const languages = facetOptions(data?.facets, "language", filters.language);
  const venues = facetOptions(data?.facets, "venue", filters.venue);
  const pageStart = data?.total ? data.offset + 1 : 0;
  const pageEnd = data ? Math.min(data.offset + data.items.length, data.total) : 0;
  const hasFilters = Object.values(initialFilters).some(Boolean);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <>
      <section className="data-section news-section">
        <div className="explorer-intro">
          <p>追踪公司公告、研发更新、论文和会议资料，并连接药物、靶点、疾病、机构及原始发布来源。</p>
        </div>

        <fieldset className="segmented-control news-display-control">
          <legend className="sr-only">动态呈现方式</legend>
          <button type="button" aria-pressed={filters.displayMode === "list"} onClick={() => changeDisplayMode("list")}>
            <List size={15} />
            动态列表
          </button>
          <button
            type="button"
            aria-pressed={filters.displayMode === "timeline"}
            onClick={() => changeDisplayMode("timeline")}
          >
            <CalendarDays size={15} />
            研究发布时间线
          </button>
          <button
            type="button"
            aria-pressed={filters.displayMode === "landscape"}
            onClick={() => changeDisplayMode("landscape")}
          >
            统计
          </button>
        </fieldset>

        <form className="domain-filter-bar news-filter-bar" onSubmit={submit} aria-label="新闻与会议筛选">
          <EntityFilterSelect
            label="关联实体"
            entityType={newsEntityTypes}
            value={filters.entityId}
            onChange={(entityId) => updateFilter("entityId", entityId)}
            placeholder="输入药品、靶点、疾病、机构或技术"
          />
          <label className="domain-query-field">
            <span>关键词</span>
            <span className="input-with-icon">
              <Search size={16} />
              <input
                value={filters.query}
                onChange={(event) => updateFilter("query", event.target.value)}
                placeholder="标题、摘要、公司、药物、靶点或疾病"
                maxLength={500}
              />
            </span>
          </label>
          <label>
            <span>事件类型</span>
            <select value={filters.eventType} onChange={(event) => updateFilter("eventType", event.target.value)}>
              <option value="">全部</option>
              {eventTypes.map((value) => (
                <option value={value} key={value}>
                  {newsEventTypeLabels[value] ?? value} ({data?.facets?.event_type?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>发布方</span>
            <select value={filters.publisher} onChange={(event) => updateFilter("publisher", event.target.value)}>
              <option value="">全部</option>
              {publishers.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.publisher?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>语言</span>
            <select value={filters.language} onChange={(event) => updateFilter("language", event.target.value)}>
              <option value="">全部</option>
              {languages.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.language?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>会议 / 场景</span>
            <select value={filters.venue} onChange={(event) => updateFilter("venue", event.target.value)}>
              <option value="">全部</option>
              {venues.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.venue?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>发布起始</span>
            <input
              type="date"
              value={filters.publishedFrom}
              onChange={(event) => updateFilter("publishedFrom", event.target.value)}
            />
          </label>
          <label>
            <span>发布截止</span>
            <input
              type="date"
              value={filters.publishedTo}
              onChange={(event) => updateFilter("publishedTo", event.target.value)}
            />
          </label>
          <div className="domain-filter-actions">
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

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel="正在查询新闻与会议动态"
          fallbackError="新闻与会议动态加载失败"
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <div className="pipeline-result-toolbar">
                <div className="result-summary">
                  <strong>{data.total}</strong>
                  <span>{initialFilters.displayMode === "timeline" ? "项研究发布" : "项最新动态"}</span>
                  <small>
                    {pageStart}-{pageEnd} · 截止 {formatDate(data.as_of, true)}
                  </small>
                </div>
                <div className="pipeline-result-actions">
                  <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!hasNewsSearchFilter(initialFilters)}
                    title={hasNewsSearchFilter(initialFilters) ? "保存或订阅当前资讯查询" : "至少应用一个查询条件"}
                    onClick={() => {
                      setSaveName(initialFilters.query.trim() || "研发事件监控");
                      setSaveMessage("");
                      setSaveOpen(true);
                    }}
                  >
                    <BookmarkPlus size={15} />
                    保存/订阅
                  </button>
                </div>
              </div>
              {filters.displayMode === "landscape" ? (
                <DomainLandscape<"event_type" | "venue">
                  domainId="news"
                  ariaLabel="资讯统计分析"
                  total={data.landscape.total_events}
                  totalUnit="条动态"
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
                      id: "venue",
                      title: "会议与期刊",
                      detail: "按会议/期刊统计完整命中集",
                      buckets: data.landscape.venue ?? [],
                      filterField: "venue",
                    },
                    {
                      id: "published-year",
                      title: "发布年份",
                      detail: "按发布年份统计完整命中集",
                      buckets: data.landscape.published_year ?? [],
                      filterField: null,
                    },
                  ]}
                  view={filters.analysisView}
                  onViewChange={(analysisView) => {
                    const next = { ...filters, analysisView };
                    setFilters(next);
                    onSearchChange(next, 0);
                  }}
                  onFilter={(field, value) => {
                    const next =
                      field === "event_type" ? { ...filters, eventType: value } : { ...filters, venue: value };
                    setFilters(next);
                    onSearchChange(next, 0);
                  }}
                />
              ) : data.items.length ? (
                initialFilters.displayMode === "timeline" ? (
                  <NewsResearchTimeline
                    items={data.items}
                    onOpenTypedEntity={openNewsEntity}
                    onOpenDetail={onNewsEventChange}
                    onOpenProvenance={setProvenanceSelection}
                  />
                ) : (
                  <VirtualDataTable
                    ariaLabel="新闻与会议结果"
                    columns={columns}
                    data={data.items}
                    getRowId={(item) => item.id}
                    preferenceKey="news-events"
                    totalRows={data.total}
                    sorting={sorting}
                    defaultSorting={defaultNewsSorting}
                    onSortingChange={changeSorting}
                    sortingScope="all"
                    toolbarActions={<DomainExportControl dataset="news" totalRows={data.total} />}
                  />
                )
              ) : (
                <EmptyState
                  title="未观察到匹配动态"
                  detail="可调整关键词、公司、药物、靶点、事件类型或日期条件后重试。"
                />
              )}
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange(initialFilters, offset)}
                ariaLabel="新闻与会议结果分页"
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
          domainLabel="新闻与会议"
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
      {selectedNewsEventId ? (
        <NewsDetailDrawer
          eventId={selectedNewsEventId}
          data={detail.data}
          loading={detail.isFetching}
          error={detail.error instanceof Error ? detail.error : null}
          onRetry={() => void detail.refetch()}
          onClose={() => onNewsEventChange(null)}
          onOpenEntity={onOpenEntity}
          onOpenTypedEntity={openNewsEntity}
          onOpenProvenance={setProvenanceSelection}
        />
      ) : null}
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}

function NewsDetailDrawer({
  eventId,
  data,
  loading,
  error,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenProvenance,
}: {
  eventId: string;
  data: NewsEventSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);
  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label="关闭新闻事件详情" onClick={onClose} />
      <aside
        ref={dialogRef}
        className="detail-drawer news-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="news-title"
        tabIndex={-1}
      >
        <header className="deal-detail-header">
          <div>
            <span>{data?.event_identifier ?? eventId}</span>
            <h2 id="news-title">{data?.title ?? "新闻事件详情"}</h2>
            {data ? (
              <div className="trial-detail-status">
                <StatusBadge value={newsEventTypeLabels[data.event_type] ?? data.event_type} />
                <span>{formatDate(data.published_at ?? "", true)}</span>
                <span>{data.venue ?? "场景未披露"}</span>
              </div>
            ) : null}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="关闭新闻事件详情"
            data-modal-autofocus="true"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {loading ? (
          <Spinner label="正在加载新闻事件详情" />
        ) : error ? (
          <ErrorState message={error.message || "新闻事件详情加载失败"} retry={onRetry} />
        ) : data ? (
          <div className="drawer-content deal-detail-content news-detail-content">
            <section>
              <h3>事件摘要</h3>
              <p>{data.summary || "摘要未披露"}</p>
              <dl className="trial-detail-grid">
                <DetailValue term="语言" value={data.language} />
                <DetailValue term="发布场景" value={data.venue} />
                <DetailValue term="补充信息" value={detailsSummary(data.details)} />
              </dl>
            </section>
            <section>
              <h3>发布方与关联实体</h3>
              <div className="deal-detail-list">
                {data.publisher_entity ? (
                  <button
                    type="button"
                    onClick={() => {
                      const entityId = data.publisher_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.publisher_entity?.entity_type ?? "organization", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.publisher_entity.name}</strong>
                    <span>发布方</span>
                  </button>
                ) : null}
                {data.related_entities.map((entity) => (
                  <button
                    key={entity.id}
                    type="button"
                    onClick={() => {
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(entity.entity_type, entity.id);
                        return;
                      }
                      onOpenEntity(entity.id);
                    }}
                  >
                    <strong>{entity.name}</strong>
                    <span>{entity.entity_type}</span>
                  </button>
                ))}
                {!data.publisher_entity && !data.related_entities.length ? <span>暂无关联实体信息</span> : null}
              </div>
            </section>
            <section>
              <h3>原始来源与证据</h3>
              {data.canonical_url ? (
                <a href={data.canonical_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={15} />
                  打开原始发布页
                </a>
              ) : null}
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? `来源文档 ${data.source_document_id}` : "来源文档未关联"}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "news_event", resourceId: data.id, label: data.title }}
                onOpen={onOpenProvenance}
              />
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
