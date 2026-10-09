import { useLocale } from "../lib/i18n";
import { newsText as t } from "../lib/i18n/news";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { NewsLandscape } from "./news/NewsLandscape";
import { NewsResultActions } from "./news/NewsResultActions";
import { newsTypeLabel } from "./news/presentation";
import "../styles/news-research.css";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarDays, List } from "lucide-react";
import { type FormEvent, useCallback, useState } from "react";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ProfessionalQueryState } from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import { ApiError } from "../lib/api";
import {
  hasNewsSearchFilter,
  loadNewsEventDetail,
  type NewsSearchFilters,
  newsKeys,
  newsSortFields,
  saveNewsSearch,
  searchNewsEvents,
  validateNewsSearchFilters,
} from "../lib/contracts/news";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import { newsEventTypeLabels } from "../lib/newsDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";
import { NewsDetailDrawer } from "./news/NewsDetailDrawer";
import { NewsFilterForm } from "./news/NewsFilterForm";
import { NewsResearchTimeline } from "./news/NewsTimeline";
import { type NewsSaveFeedback, newsSaveFeedback } from "./news/saveFeedback";
import { useNewsColumns } from "./news/useNewsColumns";

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
  useLocale();

  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [validationRequested, setValidationRequested] = useState(false);
  const validationError = validationRequested
    ? professionalValidationText(validateNewsSearchFilters(filters) ?? "")
    : "";
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveFeedback, setSaveFeedback] = useState<NewsSaveFeedback | null>(null);
  const saveMessage = newsSaveFeedback(saveFeedback);
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
    const error = validateNewsSearchFilters(filters);
    setValidationRequested(Boolean(error));
    if (error) return;
    onSearchChange({ ...filters, query: filters.query.trim() }, 0);
  }

  function clearFilters() {
    setValidationRequested(false);
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

  const columns = useNewsColumns(onNewsEventChange, openNewsEntity, setProvenanceSelection);

  const denied = result.error instanceof ApiError && [401, 403].includes(result.error.status);
  const data = denied ? undefined : result.data;
  const detailDenied = detail.error instanceof ApiError && [401, 403].includes(detail.error.status);
  const detailMismatch = !detailDenied && detail.data && detail.data.id !== selectedNewsEventId;
  const detailData = detailDenied || detailMismatch ? undefined : detail.data;
  const detailError = detailMismatch
    ? new Error(t("新闻事件与请求标识不一致"))
    : detail.error instanceof Error
      ? detail.error
      : null;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const eventTypes = facetOptions(data?.facets, "event_type", filters.eventType);
  const publishers = facetOptions(data?.facets, "publisher", filters.publisher);
  const languages = facetOptions(data?.facets, "language", filters.language);
  const venues = facetOptions(data?.facets, "venue", filters.venue);
  const hasFilters = hasNewsSearchFilter(initialFilters) || hasNewsSearchFilter(filters);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <>
      <section className="data-section news-section">
        <div className="explorer-intro">
          <p>{t("追踪公告、研究发布与会议资料，连接相关实体和原始来源。")}</p>
        </div>

        <fieldset className="segmented-control news-display-control">
          <legend className="sr-only">{t("动态呈现方式")}</legend>
          <button type="button" aria-pressed={filters.displayMode === "list"} onClick={() => changeDisplayMode("list")}>
            <List size={15} />
            {t("动态列表")}
          </button>
          <button
            type="button"
            aria-pressed={filters.displayMode === "timeline"}
            onClick={() => changeDisplayMode("timeline")}
          >
            <CalendarDays size={15} />
            {t("研究发布时间线")}
          </button>
          <button
            type="button"
            aria-pressed={filters.displayMode === "landscape"}
            onClick={() => changeDisplayMode("landscape")}
          >
            {t("统计")}
          </button>
        </fieldset>

        <NewsFilterForm
          filters={filters}
          eventTypes={eventTypes}
          publishers={publishers}
          languages={languages}
          venues={venues}
          facets={data?.facets}
          updateFilter={updateFilter}
          submit={submit}
          clearFilters={clearFilters}
          querying={result.isFetching}
          clearable={hasFilters}
          validationError={validationError}
        />

        <AppliedFiltersBar
          filters={data?.applied_filters}
          labels={Object.fromEntries(Object.entries(appliedFilterLabels).map(([key, label]) => [key, t(label)]))}
          valueLabels={{
            event_type: Object.fromEntries(Object.keys(newsEventTypeLabels).map((code) => [code, newsTypeLabel(code)])),
            content_scope: { research: t("研究发布") },
          }}
          onClear={clearFilters}
        />

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel={t("正在查询新闻与会议动态")}
          refreshingLabel={t("正在刷新新闻与会议动态")}
          fallbackError={t("新闻与会议动态加载失败")}
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <NewsResultActions
                data={data}
                displayMode={initialFilters.displayMode}
                refreshing={result.isFetching}
                saveable={hasNewsSearchFilter(initialFilters)}
                onRefresh={retryResult}
                onSave={() => {
                  setSaveName(initialFilters.query.trim() || t("研发事件监控"));
                  setSaveFeedback(null);
                  save.reset();
                  setSaveOpen(true);
                }}
              />
              {filters.displayMode === "landscape" ? (
                <NewsLandscape
                  landscape={data.landscape}
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
                    ariaLabel={t("新闻与会议结果")}
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
                <EmptyQueryResult
                  domain={t("研究动态")}
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
                ariaLabel={t("新闻与会议结果分页")}
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
          domainLabel={t("新闻与会议")}
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
      {selectedNewsEventId ? (
        <NewsDetailDrawer
          data={detailData}
          loading={detail.isFetching}
          error={detailError}
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
