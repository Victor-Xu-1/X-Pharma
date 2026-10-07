import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookmarkPlus, ExternalLink, FileText, Search } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import {
  ErrorState,
  formatDate,
  ProfessionalQueryState,
  QueryRefreshButton,
  Spinner,
  StatusBadge,
} from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { InlineEntityLinks } from "../components/InlineEntityLinks";
import { PatentLandscape } from "../components/PatentLandscape";
import { PatentTimeline } from "../components/PatentTimeline";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import { getEntity, intelligenceKeys } from "../lib/contracts/intelligence";
import {
  hasPatentSearchFilter,
  loadPatentFamilyDetail,
  type PatentSavedSearchInput,
  type PatentSortField,
  patentKeys,
  patentLegalStatusLabels,
  patentSortFields,
  type SortDirection,
  savePatentSearch,
  searchPatentFamilies,
} from "../lib/contracts/patents";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { type SortCriterion, sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { facetOptions } from "../lib/facets";
import type { EntityType, PatentFamilySearchItemRead } from "../lib/generated";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { PatentDossierSection } from "../lib/workspaceRouting";
import type { DossierEntityOpener } from "./EntityDossierView";

const PAGE_SIZE = 100;
const patentEntityTypes = ["target", "drug", "disease", "organization"] as const satisfies readonly EntityType[];
const patentRowId = (patent: PatentFamilySearchItemRead) => patent.id;
const patentEntityId = (patent: PatentFamilySearchItemRead) => patent.entity_id;
const defaultPatentSorting: SortingState = [{ id: "priority_date", desc: true }];
const patentDossierTabs: ReadonlyArray<ResearchTabOption<PatentDossierSection>> = [
  { key: "overview", label: "专利族概览" },
  { key: "timeline", label: "法律与权利要求" },
  { key: "relationships", label: "关联资产" },
];

function displayList(values: string[], empty = "--", max = 2) {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join("、");
  return values.length > max ? `${visible} 等 ${values.length} 项` : visible;
}

function publicationNumbers(values: Array<Record<string, unknown>>) {
  const identifiers = values
    .map((item) => item.publication_number ?? item.number ?? item.identifier)
    .filter((value): value is string => typeof value === "string" && Boolean(value.trim()));
  return displayList(identifiers, values.length ? `${values.length} 项公开` : "--", 2);
}

export function PatentsView({
  initialQuery,
  initialEntityId,
  initialApplicant,
  initialLegalStatus,
  initialPriorityFrom,
  initialPriorityTo,
  initialExpirationFrom,
  initialExpirationTo,
  initialSortBy,
  initialSortDirection,
  initialSort,
  initialOffset,
  displayMode,
  analysisView,
  selectedPatentId,
  activeSection,
  onSearchChange,
  onDisplayModeChange,
  onAnalysisViewChange,
  onPatentChange,
  onSectionChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  initialQuery: string;
  initialEntityId: string;
  initialApplicant: string;
  initialLegalStatus: string;
  initialPriorityFrom: string;
  initialPriorityTo: string;
  initialExpirationFrom: string;
  initialExpirationTo: string;
  initialSortBy: PatentSortField;
  initialSortDirection: SortDirection;
  initialSort?: SortCriterion<PatentSortField>[];
  initialOffset: number;
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
  selectedPatentId: string | null;
  activeSection: PatentDossierSection;
  onSearchChange: (input: PatentSavedSearchInput, offset: number) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onAnalysisViewChange: (view: "chart" | "table") => void;
  onPatentChange: (patentId: string | null) => void;
  onSectionChange: (section: PatentDossierSection, replace?: boolean) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [entityId, setEntityId] = useState(initialEntityId);
  const [entityType, setEntityType] = useState<(typeof patentEntityTypes)[number]>("target");
  const [applicant, setApplicant] = useState(initialApplicant);
  const [legalStatus, setLegalStatus] = useState(initialLegalStatus);
  const [priorityFrom, setPriorityFrom] = useState(initialPriorityFrom);
  const [priorityTo, setPriorityTo] = useState(initialPriorityTo);
  const [expirationFrom, setExpirationFrom] = useState(initialExpirationFrom);
  const [expirationTo, setExpirationTo] = useState(initialExpirationTo);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const appliedSearchInput: PatentSavedSearchInput = {
    query: initialQuery,
    entityId: initialEntityId,
    applicant: initialApplicant,
    legalStatus: initialLegalStatus,
    priorityFrom: initialPriorityFrom,
    priorityTo: initialPriorityTo,
    expirationFrom: initialExpirationFrom,
    expirationTo: initialExpirationTo,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };
  const resultQueryKey = patentKeys.search(appliedSearchInput, initialOffset);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchPatentFamilies(appliedSearchInput, initialOffset, signal),
    enabled: selectedPatentId === null,
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const selectedEntity = useQuery({
    queryKey: intelligenceKeys.entity(initialEntityId),
    queryFn: ({ signal }) => getEntity(initialEntityId, signal),
    enabled: Boolean(initialEntityId),
  });
  const detail = useQuery({
    queryKey: patentKeys.detail(selectedPatentId ?? ""),
    queryFn: ({ signal }) => loadPatentFamilyDetail(selectedPatentId ?? "", signal),
    enabled: Boolean(selectedPatentId),
  });
  const save = useMutation({ mutationFn: savePatentSearch });
  const openPatentEntity = useCallback<DossierEntityOpener>(
    (entityType, linkedEntityId) => {
      switch (entityType) {
        case "drug":
          (onOpenDrug ?? onOpenEntity)(linkedEntityId);
          return;
        case "target":
          (onOpenTarget ?? onOpenEntity)(linkedEntityId);
          return;
        case "disease":
          (onOpenDisease ?? onOpenEntity)(linkedEntityId);
          return;
        case "organization":
          (onOpenOrganization ?? onOpenEntity)(linkedEntityId);
          return;
        default:
          onOpenEntity(linkedEntityId);
      }
    },
    [onOpenDisease, onOpenDrug, onOpenEntity, onOpenOrganization, onOpenTarget],
  );

  useEffect(() => {
    setQuery(initialQuery);
    setApplicant(initialApplicant);
    setLegalStatus(initialLegalStatus);
    setEntityId(initialEntityId);
    setPriorityFrom(initialPriorityFrom);
    setPriorityTo(initialPriorityTo);
    setExpirationFrom(initialExpirationFrom);
    setExpirationTo(initialExpirationTo);
  }, [
    initialApplicant,
    initialLegalStatus,
    initialQuery,
    initialEntityId,
    initialPriorityFrom,
    initialPriorityTo,
    initialExpirationFrom,
    initialExpirationTo,
  ]);
  useEffect(() => {
    const resolvedType = selectedEntity.data?.entity_type;
    if (resolvedType && patentEntityTypes.includes(resolvedType as (typeof patentEntityTypes)[number])) {
      setEntityType(resolvedType as (typeof patentEntityTypes)[number]);
    }
  }, [selectedEntity.data?.entity_type]);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearchChange(
      {
        ...appliedSearchInput,
        query: query.trim(),
        entityId,
        applicant,
        legalStatus,
        priorityFrom,
        priorityTo,
        expirationFrom,
        expirationTo,
      },
      0,
    );
  }

  function clearFilters() {
    setQuery("");
    setEntityId("");
    setApplicant("");
    setLegalStatus("");
    setPriorityFrom("");
    setPriorityTo("");
    setExpirationFrom("");
    setExpirationTo("");
    onSearchChange(
      {
        query: "",
        entityId: "",
        applicant: "",
        legalStatus: "",
        priorityFrom: "",
        priorityTo: "",
        expirationFrom: "",
        expirationTo: "",
        sortBy: "priority_date",
        sortDirection: "desc",
        displayMode,
        analysisView,
      },
      0,
    );
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "priority_date", direction: "desc" });
    if (!sort.every((criterion) => patentSortFields.includes(criterion.field as PatentSortField))) return;
    const normalizedSort = sort as SortCriterion<PatentSortField>[];
    onSearchChange(
      {
        ...appliedSearchInput,
        sortBy: normalizedSort[0].field,
        sortDirection: normalizedSort[0].direction,
        sort: normalizedSort,
      },
      0,
    );
  }

  function changePage(offset: number) {
    onSearchChange(appliedSearchInput, offset);
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        input: appliedSearchInput,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome.message);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "专利检索保存失败");
    }
  }

  const columns = useMemo<ColumnDef<PatentFamilySearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "family_identifier",
        header: "专利族与标题",
        size: 285,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            aria-label={`打开专利族详情：${row.original.family_identifier}`}
            onClick={() => onPatentChange(row.original.id)}
          >
            <strong>{row.original.family_identifier}</strong>
            <small className="cell-subtitle">{row.original.title}</small>
          </button>
        ),
      },
      {
        accessorKey: "priority_date",
        header: "最早优先权",
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "applicants",
        header: "申请人",
        size: 165,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.applicants),
      },
      {
        accessorKey: "inventors",
        header: "发明人",
        size: 145,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.inventors),
      },
      {
        accessorKey: "publications",
        header: "公开文本",
        size: 170,
        enableSorting: false,
        cell: ({ row }) => publicationNumbers(row.original.publications),
      },
      {
        accessorKey: "legal_status",
        header: "法律状态",
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "UNKNOWN");
          return <StatusBadge value={patentLegalStatusLabels[value] ?? value} />;
        },
      },
      {
        accessorKey: "expiration_date",
        header: "预计到期",
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "timeline",
        header: "事件与权利要求",
        size: 190,
        enableSorting: false,
        cell: ({ row }) => <PatentTimeline patent={row.original} />,
      },
      {
        id: "linked_entities",
        header: "关联实体",
        size: 165,
        enableSorting: false,
        cell: ({ row }) => (
          <InlineEntityLinks
            label={`${row.original.family_identifier} 的关联实体`}
            items={row.original.linked_entities.map((entity) => ({ ...entity, key: entity.id, label: entity.name }))}
            onSelect={(entity) => openPatentEntity(entity.entity_type, entity.id)}
          />
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
            title={`打开 ${row.original.family_identifier} 档案`}
            aria-label={`打开 ${row.original.family_identifier} 档案`}
            onClick={() => onPatentChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onPatentChange, openPatentEntity],
  );

  const data = result.data;
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    patentRowId,
    patentEntityId,
  );
  const sorting: SortingState = tableSortingFromCriteria(initialSort, initialSortBy, initialSortDirection);
  const applicants = facetOptions(data?.facets, "applicant", applicant);
  const legalStatuses = facetOptions(data?.facets, "legal_status", legalStatus);
  const hasFilters = Boolean(initialQuery || initialApplicant || initialLegalStatus);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  if (selectedPatentId) {
    return (
      <>
        <PatentProfessionalDossier
          data={detail.data}
          loading={detail.isFetching}
          error={detail.error instanceof Error ? detail.error : null}
          activeSection={activeSection}
          onSectionChange={onSectionChange}
          onRetry={() => void detail.refetch()}
          onClose={() => onPatentChange(null)}
          onOpenEntity={onOpenEntity}
          onOpenTypedEntity={openPatentEntity}
          onOpenProvenance={setProvenanceSelection}
        />
        {provenanceSelection ? (
          <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
        ) : null}
      </>
    );
  }

  return (
    <>
      <section className="data-section patent-section">
        <div className="explorer-intro">
          <p>按专利族聚合优先权、申请人、发明人、公开文本、法律状态、到期时间及药物和靶点关联。</p>
        </div>

        <PublicResearchPanel defaultQuery={initialQuery} defaultTopic="patents" />

        <form className="domain-filter-bar patent-filter-bar" onSubmit={submit} aria-label="专利族筛选">
          <label className="domain-query-field">
            <span>关键词</span>
            <span className="input-with-icon">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="专利族号、标题、申请人、发明人、公开文本或关联实体"
                maxLength={500}
              />
            </span>
          </label>
          <label>
            <span>申请人</span>
            <select aria-label="申请人" value={applicant} onChange={(event) => setApplicant(event.target.value)}>
              <option value="">全部</option>
              {applicants.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.applicant?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>法律状态</span>
            <select aria-label="法律状态" value={legalStatus} onChange={(event) => setLegalStatus(event.target.value)}>
              <option value="">全部</option>
              {legalStatuses.map((value) => (
                <option value={value} key={value}>
                  {patentLegalStatusLabels[value] ?? value} ({data?.facets?.legal_status?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>关联实体类型</span>
            <select
              value={entityType}
              onChange={(event) => {
                setEntityType(event.target.value as (typeof patentEntityTypes)[number]);
                setEntityId("");
              }}
            >
              <option value="target">靶点</option>
              <option value="drug">药品</option>
              <option value="disease">疾病/适应症</option>
              <option value="organization">机构</option>
            </select>
          </label>
          <EntityFilterSelect
            label="关联实体"
            entityType={entityType}
            value={entityId}
            onChange={(nextEntityId) => setEntityId(nextEntityId)}
            placeholder="输入药品、靶点、适应症或机构"
          />
          <fieldset className="filter-range-field">
            <legend>优先权日期</legend>
            <label>
              <span>起</span>
              <input type="date" value={priorityFrom} onChange={(event) => setPriorityFrom(event.target.value)} />
            </label>
            <label>
              <span>止</span>
              <input type="date" value={priorityTo} onChange={(event) => setPriorityTo(event.target.value)} />
            </label>
          </fieldset>
          <fieldset className="filter-range-field">
            <legend>预计到期日期</legend>
            <label>
              <span>起</span>
              <input type="date" value={expirationFrom} onChange={(event) => setExpirationFrom(event.target.value)} />
            </label>
            <label>
              <span>止</span>
              <input type="date" value={expirationTo} onChange={(event) => setExpirationTo(event.target.value)} />
            </label>
          </fieldset>
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

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel="正在查询专利族"
          fallbackError="专利族查询失败"
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
                  unit="项专利族"
                  queriedAt={data.as_of}
                />
                <div className="pipeline-result-actions">
                  <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                  <fieldset className="segmented-control">
                    <legend className="sr-only">结果展示方式</legend>
                    <button
                      type="button"
                      aria-pressed={displayMode === "list"}
                      onClick={() => onDisplayModeChange("list")}
                    >
                      列表
                    </button>
                    <button
                      type="button"
                      aria-pressed={displayMode === "landscape"}
                      onClick={() => onDisplayModeChange("landscape")}
                    >
                      统计
                    </button>
                  </fieldset>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!hasPatentSearchFilter(appliedSearchInput)}
                    title={
                      hasPatentSearchFilter(appliedSearchInput) ? "保存或订阅当前专利查询" : "至少应用一个查询条件"
                    }
                    onClick={() => {
                      setSaveName(initialQuery.trim() || "专利情报监控");
                      setSaveMessage("");
                      save.reset();
                      setSaveOpen(true);
                    }}
                  >
                    <BookmarkPlus size={15} />
                    保存/订阅
                  </button>
                </div>
              </div>
              {displayMode === "landscape" ? (
                <PatentLandscape
                  landscape={data.landscape}
                  view={analysisView}
                  onViewChange={onAnalysisViewChange}
                  onFilter={(field, value) => {
                    if (field === "legal_status") {
                      setLegalStatus(value);
                      onSearchChange({ ...appliedSearchInput, legalStatus: value }, 0);
                    } else {
                      setApplicant(value);
                      onSearchChange({ ...appliedSearchInput, applicant: value }, 0);
                    }
                  }}
                />
              ) : data.items.length ? (
                <VirtualDataTable
                  ariaLabel="专利族结果"
                  columns={columns}
                  data={data.items}
                  getRowId={(patent) => patent.id}
                  preferenceKey="patent-families"
                  totalRows={data.total}
                  sorting={sorting}
                  defaultSorting={defaultPatentSorting}
                  onSortingChange={changeSorting}
                  sortingScope="all"
                  toolbarActions={
                    <>
                      <AddToComparisonControl
                        selectedEntityIds={selectedEntityIds}
                        onAdded={(message) => {
                          setSaveMessage(message);
                          clearSelection();
                        }}
                      />
                      <DomainExportControl dataset="patents" totalRows={data.total} />
                    </>
                  }
                  rowSelection={{
                    selectedRowIds,
                    onChange: onSelectionChange,
                    getRowLabel: (patent) => `对比 ${patent.family_identifier}`,
                    label: "选择对比专利族",
                    maxSelectedRows: 20,
                  }}
                />
              ) : (
                <EmptyQueryResult
                  domain="专利族"
                  filtered={Boolean(data.applied_filters?.length)}
                  onClear={clearFilters}
                />
              )}
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={changePage}
                ariaLabel="专利情报结果分页"
              />
            </div>
          ) : null}
        </ProfessionalQueryState>
      </section>
      {saveMessage && !saveOpen ? (
        <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
          {saveMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel="专利"
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
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}

function PatentProfessionalDossier({
  data,
  loading,
  error,
  activeSection,
  onSectionChange,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenProvenance,
}: {
  data: PatentFamilySearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: PatentDossierSection;
  onSectionChange: (section: PatentDossierSection, replace?: boolean) => void;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  return (
    <section className="data-section patent-professional-page" aria-labelledby="patent-title">
      <button className="trial-back-button" type="button" onClick={onClose}>
        <ArrowLeft size={17} />
        返回专利族列表
      </button>
      {loading ? (
        <Spinner label="正在加载专利族详情" />
      ) : error ? (
        <ErrorState message={error.message || "专利族详情加载失败"} retry={onRetry} />
      ) : data ? (
        <>
          <header className="patent-professional-header">
            <div>
              <span>专利族专业档案 · {data.family_identifier}</span>
              <h2 id="patent-title">{data.title}</h2>
              <div className="trial-detail-status">
                <StatusBadge
                  value={patentLegalStatusLabels[data.legal_status ?? ""] ?? data.legal_status ?? "状态未披露"}
                />
                <span>优先权 {formatDate(data.priority_date ?? "")}</span>
                <span>预计到期 {formatDate(data.expiration_date ?? "")}</span>
              </div>
            </div>
          </header>
          <dl className="dossier-metrics patent-professional-metrics" aria-label="专利族关键指标">
            <DetailValue
              term="法律状态"
              value={patentLegalStatusLabels[data.legal_status ?? ""] ?? data.legal_status}
            />
            <DetailValue term="申请人" value={String(data.applicants.length)} />
            <DetailValue term="公开文本" value={String(data.publications.length)} />
            <DetailValue term="法律事件" value={String(data.legal_events?.length ?? 0)} />
            <DetailValue term="独立权利要求" value={String(data.independent_claims?.length ?? 0)} />
            <DetailValue term="关联资产" value={String(data.linked_entities.length)} />
          </dl>
          <ResearchTabList
            tabs={patentDossierTabs}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel="专利族专业档案分区"
            idPrefix="patent-dossier"
            className="trial-professional-tabs"
          />
          <div
            id={`patent-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`patent-dossier-tab-${activeSection}`}
            className="patent-professional-body"
          >
            {activeSection === "overview" ? (
              <section>
                <h3>专利族口径</h3>
                <dl className="trial-detail-grid">
                  <DetailValue term="申请人" value={displayList(data.applicants, "未披露", 8)} />
                  <DetailValue term="发明人" value={displayList(data.inventors, "未披露", 8)} />
                  <DetailValue term="法律状态日期" value={formatDate(data.legal_status_at ?? "")} />
                  <DetailValue term="公开文本" value={publicationNumbers(data.publications)} />
                </dl>
              </section>
            ) : null}
            {activeSection === "timeline" ? (
              <section>
                <h3>法律事件与独立权利要求</h3>
                <PatentTimeline patent={data} />
              </section>
            ) : null}
            {activeSection === "relationships" ? (
              <section>
                <h3>关联实体</h3>
                <div className="deal-detail-list">
                  {data.linked_entities.length ? (
                    data.linked_entities.map((entity) => (
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
                    ))
                  ) : (
                    <span>暂无关联实体信息</span>
                  )}
                </div>
              </section>
            ) : null}
            <section>
              <h3>来源与证据</h3>
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? `来源文档 ${data.source_document_id}` : "来源文档未关联"}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "patent_family", resourceId: data.id, label: data.family_identifier }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        </>
      ) : null}
    </section>
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
