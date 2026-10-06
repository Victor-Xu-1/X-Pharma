import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  BookmarkPlus,
  Building2,
  Dna,
  FileBadge,
  FlaskConical,
  Landmark,
  List,
  Microscope,
  Search,
  Stethoscope,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { EmptyState, formatDate, ProfessionalQueryState, QueryRefreshButton } from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { type DomainAnalysisView, DomainLandscape, type DomainLandscapeSection } from "../components/DomainLandscape";
import { EntityPreviewDrawer } from "../components/EntityPreviewDrawer";
import { EntitySearchInput } from "../components/EntitySearchInput";
import { ProfessionalQueryBuilder } from "../components/ProfessionalQueryBuilder";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  type EntitySearchSortDirection,
  type EntitySearchSortField,
  type IntelligenceEntity,
  intelligenceKeys,
  saveEntitySearch,
  searchEntities,
} from "../lib/contracts/intelligence";
import {
  effectiveSort,
  type SortCriterion,
  sortCriteriaFromTable,
  tableSortingFromCriteria,
} from "../lib/contracts/sorting";
import { loadTargetProfile, targetKeys } from "../lib/contracts/target";
import { entityLabels, entityTypeLabel, matchExplanation, publicIdentifiers } from "../lib/entityPresentation";
import type { Entity } from "../lib/types";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { WorkspaceLocation } from "../lib/workspaceRouting";

const PUBLIC_REVIEW_STATUS = "verified";

// The applied-condition bar renders the server's normalized `applied_filters`, so draft
// input that has not been submitted never appears as applied query state.
const appliedFilterLabels: Record<string, string> = {
  q: "关键词",
  entity_types: "实体类型",
};

const appliedFilterValueLabels: Record<string, Record<string, string>> = {
  entity_types: entityLabels,
};

const domains = [
  { value: "", label: "全部情报", icon: Search },
  { value: "drug", label: "药物", icon: FlaskConical },
  { value: "target", label: "靶点", icon: Dna },
  { value: "organization", label: "研发机构", icon: Building2 },
  { value: "disease", label: "适应症", icon: Stethoscope },
  { value: "clinical_trial", label: "临床试验", icon: Microscope },
  { value: "patent", label: "专利", icon: FileBadge },
  { value: "transaction", label: "交易", icon: Landmark },
] as const;

const PAGE_SIZE = 100;
const intelligenceEntityId = (entity: IntelligenceEntity) => entity.id;
type ExplorerDisplayMode = "list" | "landscape";
type ExplorerLandscapeFilter = "entity_type";

function facetBuckets(
  facet: Record<string, number> | undefined,
  labels: Record<string, string>,
): DomainLandscapeSection<ExplorerLandscapeFilter>["buckets"] {
  const entries = Object.entries(facet ?? {})
    .filter(([, count]) => Number.isFinite(count) && count > 0)
    .sort(([leftKey, leftCount], [rightKey, rightCount]) => rightCount - leftCount || leftKey.localeCompare(rightKey));
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  return entries.map(([key, count]) => ({
    key,
    label: labels[key] ?? key,
    count,
    share: total > 0 ? count / total : 0,
  }));
}

function normalizeEntityTypes(values: readonly string[]): string[] {
  return Array.from(new Set(values.filter((value) => value in entityLabels))).sort();
}

function isDirectTargetMatch(entity: IntelligenceEntity, query: string): boolean {
  return Boolean(
    query.trim() &&
      entity.entity_type === "target" &&
      entity.match?.match_relation === "exact" &&
      ["canonical_name", "alias", "external_id"].includes(entity.match.match_type),
  );
}

export function ExplorerView({
  initialQuery,
  initialEntityType,
  initialEntityTypes,
  initialIncludeRelated = true,
  initialReviewStatus,
  initialSortBy = "relevance",
  initialSortDirection = "desc",
  initialSort,
  initialOffset = 0,
  initialDisplayMode = "list",
  initialAnalysisView = "chart",
  initialSelectedEntityId,
  invalidSelectedEntityId = false,
  selectedEntity: controlledSelectedEntity,
  selectedEntityLoading = false,
  selectedEntityError = "",
  onSearchChange,
  onDisplayModeChange = () => undefined,
  onAnalysisViewChange = () => undefined,
  onOpenEntity,
  onOpenTargetPipeline,
  onSelectedEntityChange,
  onOpenSpecializedSearch,
}: {
  initialQuery: string;
  initialEntityType: string;
  initialEntityTypes?: string[];
  initialIncludeRelated?: boolean;
  initialReviewStatus: string;
  initialSortBy?: string;
  initialSortDirection?: EntitySearchSortDirection;
  initialSort?: SortCriterion<EntitySearchSortField>[];
  initialOffset?: number;
  initialDisplayMode?: ExplorerDisplayMode;
  initialAnalysisView?: DomainAnalysisView;
  initialSelectedEntityId?: string | null;
  invalidSelectedEntityId?: boolean;
  selectedEntity?: Entity | null;
  selectedEntityLoading?: boolean;
  selectedEntityError?: string;
  onSearchChange: (
    query: string,
    entityTypes: string[],
    reviewStatus: string,
    sortBy: EntitySearchSortField,
    sortDirection: EntitySearchSortDirection,
    offset: number,
    sort?: SortCriterion<EntitySearchSortField>[],
    includeRelated?: boolean,
  ) => void;
  onDisplayModeChange?: (displayMode: ExplorerDisplayMode) => void;
  onAnalysisViewChange?: (analysisView: DomainAnalysisView) => void;
  onOpenEntity: (entity: Entity) => void;
  onOpenTargetPipeline?: (targetId: string) => void;
  onSelectedEntityChange?: (entity: Entity | null) => void;
  onOpenSpecializedSearch: (location: WorkspaceLocation) => void;
}) {
  const initialEntityTypesKey = (initialEntityTypes ?? []).join(",");
  const requestedInitialEntityTypes = useMemo(
    () =>
      normalizeEntityTypes(
        initialEntityTypesKey ? initialEntityTypesKey.split(",") : initialEntityType ? [initialEntityType] : [],
      ),
    [initialEntityType, initialEntityTypesKey],
  );
  const [query, setQuery] = useState(initialQuery);
  const [selectedEntityTypes, setSelectedEntityTypes] = useState(requestedInitialEntityTypes);
  const searchInputRef = useRef<{ close: () => void }>(null);
  const [localSelectedEntity, setLocalSelectedEntity] = useState<IntelligenceEntity | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [shared, setShared] = useState(false);
  const [monitor, setMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");

  const searchQueryKey = intelligenceKeys.search(
    initialQuery,
    requestedInitialEntityTypes,
    PUBLIC_REVIEW_STATUS,
    initialSortBy as EntitySearchSortField,
    initialSortDirection,
    initialOffset,
    initialSort,
    initialIncludeRelated,
  );
  const searchEnabled = Boolean(initialQuery || requestedInitialEntityTypes.length || initialReviewStatus);
  const search = useQuery({
    queryKey: searchQueryKey,
    queryFn: ({ signal }) =>
      searchEntities(initialQuery, requestedInitialEntityTypes, PUBLIC_REVIEW_STATUS, signal, {
        sortBy: initialSortBy as EntitySearchSortField,
        sortDirection: initialSortDirection,
        sort: initialSort,
        offset: initialOffset,
        includeRelated: initialIncludeRelated,
      }),
    enabled: searchEnabled,
  });
  const queryCancellation = useQueryCancellation(searchQueryKey);
  const {
    selectedRowIds: selectedEntityIds,
    onSelectionChange: setSelectedEntityIds,
    clearSelection: clearSelectedEntities,
  } = usePagedEntitySelection(search.data?.items ?? [], intelligenceEntityId, intelligenceEntityId);
  const save = useMutation({
    mutationFn: saveEntitySearch,
    onSuccess: ({ message }) => {
      setSaveMessage(message);
      setSaveOpen(false);
      setSaveName("");
    },
    onError: (caught) => setSaveMessage(caught instanceof Error ? caught.message : "保存失败"),
  });
  useEffect(() => {
    setQuery(initialQuery);
    setSelectedEntityTypes(requestedInitialEntityTypes);
    clearSelectedEntities();
  }, [clearSelectedEntities, initialQuery, requestedInitialEntityTypes]);

  useEffect(() => {
    if (!initialReviewStatus || initialReviewStatus === PUBLIC_REVIEW_STATUS) return;
    onSearchChange(
      initialQuery,
      requestedInitialEntityTypes,
      PUBLIC_REVIEW_STATUS,
      initialSortBy as EntitySearchSortField,
      initialSortDirection,
      0,
      initialSort,
    );
  }, [
    initialQuery,
    initialReviewStatus,
    initialSort,
    initialSortBy,
    initialSortDirection,
    onSearchChange,
    requestedInitialEntityTypes,
  ]);

  useEffect(() => {
    if (initialSelectedEntityId !== undefined && localSelectedEntity?.id !== initialSelectedEntityId) {
      setLocalSelectedEntity(null);
    }
  }, [initialSelectedEntityId, localSelectedEntity?.id]);

  function runSearch(nextQuery = query, nextTypes = selectedEntityTypes) {
    const normalizedQuery = nextQuery.trim();
    const normalizedTypes = normalizeEntityTypes(nextTypes);
    searchInputRef.current?.close();
    if (
      normalizedQuery === initialQuery &&
      normalizedTypes.join(",") === requestedInitialEntityTypes.join(",") &&
      initialReviewStatus === PUBLIC_REVIEW_STATUS &&
      initialOffset === 0
    ) {
      queryCancellation.reset();
      void search.refetch();
    } else {
      onSearchChange(
        normalizedQuery,
        normalizedTypes,
        PUBLIC_REVIEW_STATUS,
        initialSortBy as EntitySearchSortField,
        initialSortDirection,
        0,
        initialSort,
      );
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    runSearch();
  }

  function chooseDomain(nextType: string) {
    const nextTypes = nextType
      ? selectedEntityTypes.includes(nextType)
        ? selectedEntityTypes.filter((value) => value !== nextType)
        : [...selectedEntityTypes, nextType]
      : [];
    setSelectedEntityTypes(nextTypes);
    runSearch(query, nextTypes);
  }

  function saveSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    save.mutate({
      name: saveName,
      query: initialQuery,
      entityTypes: requestedInitialEntityTypes,
      reviewStatus: PUBLIC_REVIEW_STATUS,
      sortBy: initialSortBy as EntitySearchSortField,
      sortDirection: initialSortDirection,
      sort: initialSort,
      displayMode: initialDisplayMode,
      analysisView: initialAnalysisView,
      shared,
      monitor,
      includeRelated: initialIncludeRelated,
    });
  }

  const columns = useMemo<ColumnDef<IntelligenceEntity, unknown>[]>(
    () => [
      {
        accessorKey: "name",
        header: "名称",
        size: 300,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            onClick={() => {
              setLocalSelectedEntity(row.original);
              onSelectedEntityChange?.(row.original);
            }}
            aria-label={row.original.name}
          >
            <strong>{row.original.name}</strong>
            {matchExplanation(row.original) ? (
              <small className="entity-match-context">{matchExplanation(row.original)}</small>
            ) : null}
            {row.original.description ? <small className="cell-subtitle">{row.original.description}</small> : null}
          </button>
        ),
      },
      {
        accessorKey: "entity_type",
        header: "类型",
        size: 120,
        cell: ({ row }) => entityTypeLabel(row.original),
      },
      {
        id: "external_ids",
        header: "外部标识",
        size: 250,
        enableSorting: false,
        cell: ({ row }) => {
          const identifiers = publicIdentifiers(row.original).slice(0, 2);
          return (
            <div className="external-id-cell">
              {identifiers.map(([key, value]) => (
                <span key={key}>
                  {key}: {value}
                </span>
              ))}
              {!identifiers.length ? <span>暂无外部标识</span> : null}
            </div>
          );
        },
      },
      {
        accessorKey: "updated_at",
        header: "更新时间",
        size: 175,
        cell: ({ getValue }) => formatDate(String(getValue())),
      },
      {
        id: "actions",
        header: "操作",
        size: 104,
        enableSorting: false,
        cell: ({ row }) => (
          <div className="row-actions">
            {row.original.entity_type === "target" && onOpenTargetPipeline ? (
              <button
                className="icon-button"
                type="button"
                onClick={() => onOpenTargetPipeline(row.original.id)}
                title="查看研发项目"
                aria-label={`查看 ${row.original.name} 研发项目`}
              >
                <FlaskConical size={17} />
              </button>
            ) : null}
            <button
              className="icon-button"
              type="button"
              onClick={() => {
                setLocalSelectedEntity(row.original);
                onSelectedEntityChange?.(row.original);
              }}
              title="查看实体详情"
              aria-label={`查看 ${row.original.name} 实体详情`}
            >
              <ArrowRight size={17} />
            </button>
          </div>
        ),
      },
    ],
    [onOpenTargetPipeline, onSelectedEntityChange],
  );

  // A large real page must not monopolize the main thread while the user is
  // still interacting with the query surface or table controls.
  // React Query owns the applied result snapshot. Route updates already use a
  // transition; deferring this snapshot again can leave an empty or obsolete
  // result surface after the authoritative request has completed.
  const result = search.data;
  const directTarget = useMemo(() => {
    if (
      !result ||
      !onOpenTargetPipeline ||
      !initialQuery.trim() ||
      (requestedInitialEntityTypes.length > 0 && !requestedInitialEntityTypes.includes("target"))
    ) {
      return null;
    }
    return result.items.find((entity) => isDirectTargetMatch(entity, initialQuery)) ?? null;
  }, [initialQuery, onOpenTargetPipeline, requestedInitialEntityTypes, result]);
  const directTargetProfile = useQuery({
    queryKey: targetKeys.profile(directTarget?.id ?? ""),
    queryFn: ({ signal }) => loadTargetProfile(directTarget?.id ?? "", signal),
    enabled: Boolean(directTarget),
  });
  const displayedEntityTypeCount = (entityType: string) =>
    !entityType
      ? selectedEntityTypes.length === 0
        ? result?.total
        : undefined
      : selectedEntityTypes.length === 1 && selectedEntityTypes[0] === entityType
        ? result?.total
        : result?.facets.entity_type?.[entityType];
  const landscapeSections = useMemo<DomainLandscapeSection<ExplorerLandscapeFilter>[]>(
    () => [
      {
        id: "entity-type",
        title: "实体类型",
        detail: "按实体类型统计当前完整命中集",
        buckets: facetBuckets(result?.facets.entity_type, entityLabels),
        filterField: "entity_type",
      },
    ],
    [result?.facets.entity_type],
  );
  const selectedEntity =
    initialSelectedEntityId === undefined || localSelectedEntity?.id === initialSelectedEntityId
      ? localSelectedEntity
      : controlledSelectedEntity?.id === initialSelectedEntityId
        ? controlledSelectedEntity
        : null;
  const selectedEntityRequested = Boolean(
    selectedEntity ||
      initialSelectedEntityId ||
      invalidSelectedEntityId ||
      selectedEntityLoading ||
      selectedEntityError,
  );
  const canSubmit = Boolean(query.trim() || selectedEntityTypes.length);
  const activeDomain =
    selectedEntityTypes.length === 0
      ? "全部情报"
      : selectedEntityTypes.length === 1
        ? (entityLabels[selectedEntityTypes[0] ?? ""] ?? selectedEntityTypes[0])
        : `已选 ${selectedEntityTypes.length} 类`;
  const entitySort = effectiveSort(
    initialSort,
    (initialSortBy ?? "relevance") as EntitySearchSortField,
    initialSortDirection ?? "desc",
  );
  const visibleEntitySort = entitySort.filter((criterion) => criterion.field !== "relevance");
  const visiblePrimarySort = visibleEntitySort[0];
  const tableSorting: SortingState = tableSortingFromCriteria(
    visibleEntitySort,
    visiblePrimarySort?.field ?? "relevance",
    visiblePrimarySort?.direction ?? "desc",
  ).filter((criterion) => criterion.id !== "relevance");

  function retrySearch() {
    queryCancellation.reset();
    void search.refetch();
  }

  function changeSorting(sorting: SortingState) {
    const sort = sortCriteriaFromTable(sorting, { field: "relevance", direction: "desc" });
    const primary = sort[0];
    onSearchChange(
      initialQuery,
      requestedInitialEntityTypes,
      PUBLIC_REVIEW_STATUS,
      primary.field,
      primary.direction,
      0,
      sort,
    );
  }

  function changePage(offset: number) {
    onSearchChange(
      initialQuery,
      requestedInitialEntityTypes,
      PUBLIC_REVIEW_STATUS,
      initialSortBy as EntitySearchSortField,
      initialSortDirection,
      Math.max(0, offset),
      initialSort,
    );
  }

  function filterFromLandscape(_field: ExplorerLandscapeFilter, value: string) {
    onSearchChange(
      initialQuery,
      [value],
      PUBLIC_REVIEW_STATUS,
      initialSortBy as EntitySearchSortField,
      initialSortDirection,
      0,
      initialSort,
    );
  }

  return (
    <section className="data-section explorer-section">
      <form className="intelligence-query-panel" onSubmit={submit}>
        <div className="query-row">
          <label htmlFor="intelligence-query">查询对象</label>
          <EntitySearchInput
            query={query}
            entityTypes={selectedEntityTypes}
            domainLabel={activeDomain}
            onQueryChange={setQuery}
            onSearch={runSearch}
            controlRef={searchInputRef}
          />
          <button className="primary-button" type="submit" disabled={search.isFetching || !canSubmit}>
            <Search size={16} />
            检索
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={!initialQuery.trim() && !requestedInitialEntityTypes.length}
            title="保存当前已执行的查询条件"
            onClick={() => {
              setSaveName(initialQuery.trim() || "已执行检索监控");
              setSaveOpen(true);
              setSaveMessage("");
            }}
          >
            <BookmarkPlus size={16} />
            保存检索
          </button>
        </div>
        <div className="query-row filter-row">
          <span className="query-label">对象类型</span>
          <fieldset className="inline-filter-options domain-filter-options">
            <legend className="sr-only">情报对象类型</legend>
            {domains.map(({ value, label, icon: Icon }) => (
              <button
                className={
                  value
                    ? selectedEntityTypes.includes(value)
                      ? "selected"
                      : ""
                    : selectedEntityTypes.length === 0
                      ? "selected"
                      : ""
                }
                type="button"
                key={value || "all"}
                onClick={() => chooseDomain(value)}
                aria-pressed={value ? selectedEntityTypes.includes(value) : selectedEntityTypes.length === 0}
                aria-label={`对象类型：${label}${
                  displayedEntityTypeCount(value) !== undefined ? `，${displayedEntityTypeCount(value)} 条` : ""
                }`}
              >
                <Icon size={14} />
                {label}
                {displayedEntityTypeCount(value) !== undefined ? <span>{displayedEntityTypeCount(value)}</span> : null}
              </button>
            ))}
          </fieldset>
        </div>
        <details className="advanced-filters explorer-professional-query">
          <summary>
            高级条件查询
            <span>按药物、靶点、机构、阶段等组合筛选</span>
          </summary>
          <ProfessionalQueryBuilder query={query.trim()} onExecute={onOpenSpecializedSearch} />
        </details>
        <label
          className="checkbox-field"
          title="从精确名称、别名或标识出发，仅扩展一层有当前已发布证据的关系，不推断机制或获批用途。"
        >
          <input
            type="checkbox"
            checked={initialIncludeRelated}
            onChange={(event) =>
              onSearchChange(
                initialQuery,
                requestedInitialEntityTypes,
                PUBLIC_REVIEW_STATUS,
                initialSortBy as EntitySearchSortField,
                initialSortDirection,
                0,
                initialSort,
                event.target.checked,
              )
            }
          />
          包含已验证关联
        </label>
      </form>

      <PublicResearchPanel defaultQuery={initialQuery} />
      {result && requestedInitialEntityTypes.length ? (
        <p className="inline-feedback">当前结果仅统计已选对象类型；点击“全部情报”重新查询完整范围。</p>
      ) : null}
      {result?.warnings?.map((warning) => (
        <p className="inline-feedback" role="status" key={warning}>
          {warning}
        </p>
      ))}
      <AppliedFiltersBar
        filters={result?.applied_filters?.filter(
          (filter) => !["review_status", "include_related"].includes(filter.field),
        )}
        labels={appliedFilterLabels}
        valueLabels={appliedFilterValueLabels}
        onClear={() => {
          setQuery("");
          setSelectedEntityTypes([]);
          onSearchChange("", [], PUBLIC_REVIEW_STATUS, "relevance", "desc", 0);
        }}
      />

      {saveMessage ? (
        <p className="inline-feedback" role="status">
          {saveMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel=""
        name={saveName}
        shared={shared}
        monitor={monitor}
        pending={save.isPending}
        onNameChange={setSaveName}
        onSharedChange={setShared}
        onMonitorChange={setMonitor}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void saveSearch(event)}
      />

      <ProfessionalQueryState
        dataAvailable={Boolean(result)}
        enabled={searchEnabled}
        isFetching={search.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={search.error}
        loadingLabel="正在检索结构化情报"
        fallbackError="结构化情报查询失败"
        onCancel={queryCancellation.cancel}
        onRetry={retrySearch}
        onDismissCancellation={queryCancellation.reset}
        idle={<EmptyState title="输入检索条件" detail="支持药物、靶点、公司、疾病、临床试验、专利与交易" />}
      >
        {result ? (
          <div className="explorer-results">
            {directTarget && onOpenTargetPipeline ? (
              <section
                className="pipeline-result-toolbar target-direct-access"
                aria-label={`${directTarget.name} 靶点直达`}
              >
                <div className="result-summary">
                  <strong>{directTarget.name}</strong>
                  <span>靶点精确命中</span>
                  <small>
                    {matchExplanation(directTarget) ?? "已识别为靶点"} ·{" "}
                    {directTargetProfile.data
                      ? `已关联 ${directTargetProfile.data.program_count.toLocaleString("zh-CN")} 个研发项目，可继续按药物、阶段、机构、适应症与作用机制筛选`
                      : "进入后查看药物、阶段、机构、适应症与作用机制"}
                  </small>
                </div>
                <div className="pipeline-result-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => onOpenTargetPipeline(directTarget.id)}
                  >
                    {directTargetProfile.data
                      ? `查看 ${directTargetProfile.data.program_count.toLocaleString("zh-CN")} 个研发项目`
                      : "查看全部研发项目"}
                    <ArrowRight size={15} />
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      setLocalSelectedEntity(directTarget);
                      onSelectedEntityChange?.(directTarget);
                    }}
                  >
                    查看靶点详情
                  </button>
                </div>
              </section>
            ) : null}
            {result.total > 0 ? (
              <div className="pipeline-result-toolbar">
                <div className="result-summary">
                  <strong>{result.total}</strong>
                  <span>条匹配结果</span>
                </div>
                <div className="pipeline-result-actions">
                  <QueryRefreshButton refreshing={search.isFetching} onRefresh={retrySearch} />
                  <fieldset className="segmented-control">
                    <legend className="sr-only">实体结果展示方式</legend>
                    <button
                      type="button"
                      aria-pressed={initialDisplayMode === "list"}
                      onClick={() => onDisplayModeChange("list")}
                    >
                      <List size={14} />
                      列表
                    </button>
                    <button
                      type="button"
                      aria-pressed={initialDisplayMode === "landscape"}
                      onClick={() => onDisplayModeChange("landscape")}
                    >
                      <BarChart3 size={14} />
                      统计
                    </button>
                  </fieldset>
                </div>
              </div>
            ) : (
              <div className="result-summary">
                <strong>{result.total}</strong>
                <span>条匹配结果</span>
              </div>
            )}
            {initialDisplayMode === "landscape" && result.total > 0 ? (
              <DomainLandscape
                domainId="entities"
                ariaLabel="实体检索统计分析"
                total={result.total}
                totalUnit="条实体"
                unitLabel="实体数"
                sections={landscapeSections}
                view={initialAnalysisView}
                onViewChange={onAnalysisViewChange}
                onFilter={filterFromLandscape}
              />
            ) : result.items.length ? (
              <VirtualDataTable
                ariaLabel="实体检索结果"
                columns={columns}
                data={result.items}
                getRowId={(entity) => entity.id}
                preferenceKey="entity-search"
                totalRows={result.total}
                sorting={tableSorting}
                defaultSorting={[]}
                defaultSortingDescription="按相关性降序"
                onSortingChange={changeSorting}
                sortingScope="all"
                toolbarActions={
                  <>
                    <AddToComparisonControl
                      selectedEntityIds={selectedEntityIds}
                      onAdded={(message) => {
                        setSaveMessage(message);
                        clearSelectedEntities();
                      }}
                    />
                    <DomainExportControl dataset="entities" totalRows={result.total} />
                  </>
                }
                rowSelection={{
                  selectedRowIds: selectedEntityIds,
                  onChange: setSelectedEntityIds,
                  getRowLabel: (entity) => `对比 ${entity.name}`,
                  label: "选择对比实体",
                  maxSelectedRows: 20,
                }}
              />
            ) : (
              <EmptyState title="未找到匹配实体" detail="请调整名称、情报领域或更多筛选" />
            )}
            {initialDisplayMode === "list" && result.total > 0 ? (
              <ResultPagination
                totalRows={result.total}
                offset={result.offset}
                pageSize={PAGE_SIZE}
                onPageChange={changePage}
                ariaLabel="实体检索结果分页"
              />
            ) : null}
          </div>
        ) : null}
      </ProfessionalQueryState>

      <EntityPreviewDrawer
        active={selectedEntityRequested}
        entity={selectedEntity}
        invalidId={invalidSelectedEntityId}
        loading={selectedEntityLoading}
        error={selectedEntityError}
        onClose={() => {
          setLocalSelectedEntity(null);
          onSelectedEntityChange?.(null);
        }}
        onOpenEntity={onOpenEntity}
        onOpenTargetPipeline={onOpenTargetPipeline}
      />
    </section>
  );
}
