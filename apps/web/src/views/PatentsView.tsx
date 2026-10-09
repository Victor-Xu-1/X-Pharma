import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { ProfessionalQueryState } from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { PatentLandscape } from "../components/PatentLandscape";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import { ApiError } from "../lib/api";
import { getEntity, intelligenceKeys } from "../lib/contracts/intelligence";
import {
  emptyPatentSearchFilters,
  hasPatentSearchFilter,
  loadPatentFamilyDetail,
  type PatentSavedSearchInput,
  type PatentSearchFilters,
  type PatentSortField,
  patentKeys,
  patentSortFields,
  type SortDirection,
  savePatentSearch,
  searchPatentFamilies,
  validatePatentSearchFilters,
} from "../lib/contracts/patents";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { type SortCriterion, sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import type { PatentFamilySearchItemRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { patentText as t } from "../lib/i18n/patents";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { PatentDossierSection } from "../lib/workspaceRouting";
import type { DossierEntityOpener } from "./EntityDossierView";
import { usePatentColumns } from "./patents/columns";
import { type PatentEntityType, PatentFilterForm, patentEntityTypes } from "./patents/PatentFilterForm";
import { PatentProfessionalDossier } from "./patents/PatentProfessionalDossier";
import { PatentResultActions } from "./patents/PatentResultActions";
import { type PatentSaveFeedback, patentSaveFeedback } from "./patents/saveFeedback";
import "./patents/patents.css";

const PAGE_SIZE = 100;
const patentRowId = (patent: PatentFamilySearchItemRead) => patent.id;
const patentEntityId = (patent: PatentFamilySearchItemRead) => patent.entity_id;
const defaultPatentSorting: SortingState = [{ id: "priority_date", desc: true }];

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
  useLocale();
  const appliedFilters = useMemo<PatentSearchFilters>(
    () => ({
      query: initialQuery,
      entityId: initialEntityId,
      applicant: initialApplicant,
      legalStatus: initialLegalStatus,
      priorityFrom: initialPriorityFrom,
      priorityTo: initialPriorityTo,
      expirationFrom: initialExpirationFrom,
      expirationTo: initialExpirationTo,
    }),
    [
      initialQuery,
      initialEntityId,
      initialApplicant,
      initialLegalStatus,
      initialPriorityFrom,
      initialPriorityTo,
      initialExpirationFrom,
      initialExpirationTo,
    ],
  );
  const appliedSearchInput: PatentSavedSearchInput = {
    ...appliedFilters,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };
  const [filters, setFilters] = useFilterDraft(appliedFilters);
  const [entityType, setEntityType] = useState<PatentEntityType>("target");
  const [validationError, setValidationError] = useState<ReturnType<typeof validatePatentSearchFilters>>(null);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveFeedback, setSaveFeedback] = useState<PatentSaveFeedback | null>(null);
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
    (type, id) => {
      switch (type) {
        case "drug":
          (onOpenDrug ?? onOpenEntity)(id);
          return;
        case "target":
          (onOpenTarget ?? onOpenEntity)(id);
          return;
        case "disease":
          (onOpenDisease ?? onOpenEntity)(id);
          return;
        case "organization":
          (onOpenOrganization ?? onOpenEntity)(id);
          return;
        default:
          onOpenEntity(id);
      }
    },
    [onOpenDisease, onOpenDrug, onOpenEntity, onOpenOrganization, onOpenTarget],
  );

  useEffect(() => {
    const resolvedType = selectedEntity.data?.id === initialEntityId ? selectedEntity.data.entity_type : null;
    if (resolvedType && patentEntityTypes.includes(resolvedType as PatentEntityType))
      setEntityType(resolvedType as PatentEntityType);
  }, [initialEntityId, selectedEntity.data]);
  useEffect(() => {
    if (filters === appliedFilters) setValidationError(null);
  }, [filters, appliedFilters]);

  function updateFilter<K extends keyof PatentSearchFilters>(key: K, value: PatentSearchFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setValidationError(null);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const error = validatePatentSearchFilters(filters);
    if (error) {
      setValidationError(error);
      return;
    }
    onSearchChange({ ...appliedSearchInput, ...filters, query: filters.query.trim() }, 0);
  }
  function clearFilters() {
    setFilters(emptyPatentSearchFilters);
    setValidationError(null);
    onSearchChange(
      { ...emptyPatentSearchFilters, sortBy: "priority_date", sortDirection: "desc", displayMode, analysisView },
      0,
    );
  }
  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "priority_date", direction: "desc" });
    if (!sort.every((criterion) => patentSortFields.includes(criterion.field as PatentSortField))) return;
    const normalized = sort as SortCriterion<PatentSortField>[];
    onSearchChange(
      { ...appliedSearchInput, sortBy: normalized[0].field, sortDirection: normalized[0].direction, sort: normalized },
      0,
    );
  }
  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    if (save.isPending) return;
    setSaveFeedback(null);
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        input: appliedSearchInput,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveFeedback({ kind: "outcome", outcome });
    } catch (error) {
      setSaveFeedback({ kind: "error", reason: error instanceof Error ? error.message : null });
    }
  }
  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  const resultDenied = result.error instanceof ApiError && [401, 403].includes(result.error.status);
  const data = resultDenied ? undefined : result.data;
  const detailDenied = detail.error instanceof ApiError && [401, 403].includes(detail.error.status);
  const detailMismatch = !detailDenied && detail.data && detail.data.id !== selectedPatentId;
  const detailData = detailDenied || detailMismatch ? undefined : detail.data;
  const detailError = detailMismatch
    ? new Error(t("专利详情与请求标识不一致"))
    : detail.error instanceof Error
      ? detail.error
      : null;
  const columns = usePatentColumns(onPatentChange, openPatentEntity);
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    patentRowId,
    patentEntityId,
  );
  const sorting = tableSortingFromCriteria(initialSort, initialSortBy, initialSortDirection);
  const clearable =
    hasPatentSearchFilter(appliedSearchInput) || hasPatentSearchFilter({ ...appliedSearchInput, ...filters });
  const feedbackMessage = patentSaveFeedback(saveFeedback);

  if (selectedPatentId)
    return (
      <>
        <PatentProfessionalDossier
          data={detailData}
          loading={detail.isFetching}
          error={detailError}
          activeSection={activeSection}
          onSectionChange={onSectionChange}
          onRetry={() => void detail.refetch()}
          onClose={() => onPatentChange(null)}
          onOpenTypedEntity={openPatentEntity}
          onOpenProvenance={setProvenanceSelection}
        />
        {provenanceSelection ? (
          <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
        ) : null}
      </>
    );

  return (
    <>
      <section className="data-section patent-section">
        <div className="explorer-intro">
          <p>{t("检索专利族、法律事件与关联资产，核对原始文本和数据时点。")}</p>
        </div>
        <PublicResearchPanel defaultQuery={initialQuery} defaultTopic="patents" />
        <PatentFilterForm
          filters={filters}
          facets={data?.facets}
          entityType={entityType}
          onEntityType={(type) => {
            setEntityType(type);
            updateFilter("entityId", "");
          }}
          update={updateFilter}
          submit={submit}
          clear={clearFilters}
          querying={result.isFetching}
          clearable={clearable}
          validationError={validationError ? t(validationError) : ""}
        />
        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel={t("正在查询专利族")}
          refreshingLabel={t("正在刷新专利族")}
          fallbackError={t("专利族查询失败")}
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <PatentResultActions
                data={data}
                refreshing={result.isFetching}
                displayMode={displayMode}
                saveable={hasPatentSearchFilter(appliedSearchInput)}
                onRefresh={retryResult}
                onDisplayMode={onDisplayModeChange}
                onSave={() => {
                  setSaveName(initialQuery.trim() || t("专利情报监控"));
                  setSaveFeedback(null);
                  save.reset();
                  setSaveOpen(true);
                }}
              />
              {displayMode === "landscape" ? (
                <PatentLandscape
                  landscape={data.landscape}
                  view={analysisView}
                  onViewChange={onAnalysisViewChange}
                  onFilter={(field, value) => {
                    const key = field === "legal_status" ? "legalStatus" : "applicant";
                    updateFilter(key, value);
                    onSearchChange({ ...appliedSearchInput, [key]: value }, 0);
                  }}
                />
              ) : data.items.length ? (
                <VirtualDataTable
                  ariaLabel={t("专利族结果")}
                  columns={columns}
                  data={data.items}
                  getRowId={patentRowId}
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
                          setSaveFeedback({ kind: "comparison", message });
                          clearSelection();
                        }}
                      />
                      <DomainExportControl dataset="patents" totalRows={data.total} />
                    </>
                  }
                  rowSelection={{
                    selectedRowIds,
                    onChange: onSelectionChange,
                    getRowLabel: (patent) => t("对比 {identifier}", { identifier: patent.family_identifier }),
                    label: t("选择对比专利族"),
                    maxSelectedRows: 20,
                  }}
                />
              ) : (
                <EmptyQueryResult
                  domain={t("专利族")}
                  filtered={Boolean(data.applied_filters?.length)}
                  onClear={clearFilters}
                />
              )}
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange(appliedSearchInput, offset)}
                ariaLabel={t("专利情报结果分页")}
              />
            </div>
          ) : null}
        </ProfessionalQueryState>
      </section>
      {feedbackMessage && !saveOpen ? (
        <p
          className={saveFeedback?.kind === "error" ? "inline-error" : "inline-feedback"}
          role={saveFeedback?.kind === "error" ? "alert" : "status"}
        >
          {feedbackMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel={t("专利")}
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        error={saveFeedback?.kind === "error" ? feedbackMessage : ""}
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
