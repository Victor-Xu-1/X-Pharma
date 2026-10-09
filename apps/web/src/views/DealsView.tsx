import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ProfessionalQueryState } from "../components/common";
import { DealLandscape, type DealLandscapeFilterField } from "../components/DealLandscape";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import { ApiError } from "../lib/api";
import {
  type DealAnalysisDimension,
  type DealAnalysisLimit,
  type DealAnalysisView,
  type DealSearchFilters,
  dealKeys,
  dealSortFields,
  emptyDealSearchFilters,
  hasDealSearchFilter,
  loadDealDetail,
  saveDealSearch,
  searchDeals,
  validateDealSearchFilters,
} from "../lib/contracts/deals";
import { intelligenceKeys, searchEntities } from "../lib/contracts/intelligence";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { getSessionEntity, sessionKeys } from "../lib/contracts/session";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import {
  dealTypeLabels,
  directionLabels,
  localizedDealLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../lib/dealDisplay";
import type { DealSearchItemRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { dealText as t } from "../lib/i18n/deals";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DealDossierSection } from "../lib/workspaceRouting";
import { appliedDealFilterLabels } from "./deals/appliedPresentation";
import { DealFilterForm } from "./deals/DealFilterForm";
import { DealProfessionalDossier } from "./deals/DealProfessionalDossier";
import { DealResultActions } from "./deals/DealResultActions";
import { type DealSaveFeedback, dealSaveFeedback } from "./deals/saveFeedback";
import { useDealColumns } from "./deals/useDealColumns";
import type { DossierEntityOpener } from "./EntityDossierView";
import "./deals/deals.css";

const PAGE_SIZE = 100;
const dealRowId = (deal: DealSearchItemRead) => deal.id;
const dealEntityId = (deal: DealSearchItemRead) => deal.entity_id;
const amountSortFields = new Set<DealSearchFilters["sortBy"]>(["upfront_amount", "total_potential_amount"]);

function useDebouncedValue(value: string, delay: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

export function DealsView({
  displayMode,
  analysisDimension,
  analysisView,
  analysisLimit,
  initialFilters,
  initialOffset,
  selectedDealId,
  activeSection,
  onSearchChange,
  onDisplayModeChange,
  onAnalysisChange,
  onDealChange,
  onSectionChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  displayMode: "list" | "landscape";
  analysisDimension: DealAnalysisDimension;
  analysisView: DealAnalysisView;
  analysisLimit: DealAnalysisLimit;
  initialFilters: DealSearchFilters;
  initialOffset: number;
  selectedDealId: string | null;
  activeSection: DealDossierSection;
  onSearchChange: (filters: DealSearchFilters, offset: number) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onAnalysisChange: (next: {
    dimension: DealAnalysisDimension;
    view: DealAnalysisView;
    limit: DealAnalysisLimit;
  }) => void;
  onDealChange: (dealId: string | null) => void;
  onSectionChange: (section: DealDossierSection, replace?: boolean) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  useLocale();
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false),
    [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false),
    [saveMonitor, setSaveMonitor] = useState(true);
  const [saveFeedback, setSaveFeedback] = useState<DealSaveFeedback | null>(null);
  const debouncedParty = useDebouncedValue(filters.party.trim(), 250);
  const resultQueryKey = dealKeys.search(initialFilters, initialOffset, analysisLimit);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchDeals(initialFilters, initialOffset, analysisLimit, signal),
    enabled: selectedDealId === null,
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const detail = useQuery({
    queryKey: dealKeys.detail(selectedDealId ?? ""),
    queryFn: ({ signal }) => loadDealDetail(selectedDealId ?? "", signal),
    enabled: Boolean(selectedDealId),
  });
  const selectedParty = useQuery({
    queryKey: sessionKeys.entity(initialFilters.partyEntityId),
    queryFn: ({ signal }) => getSessionEntity(initialFilters.partyEntityId, signal),
    enabled: selectedDealId === null && Boolean(initialFilters.partyEntityId && !initialFilters.party),
  });
  const partySuggestions = useQuery({
    queryKey: intelligenceKeys.search(debouncedParty, ["organization"], ""),
    queryFn: ({ signal }) => searchEntities(debouncedParty, ["organization"], "", signal),
    enabled: selectedDealId === null && debouncedParty.length >= 2 && !filters.partyEntityId,
  });
  const save = useMutation({ mutationFn: saveDealSearch });
  const openDealEntity = useCallback<DossierEntityOpener>(
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
    if (filters === initialFilters) setValidationError(null);
  }, [filters, initialFilters]);
  useEffect(() => {
    if (
      !initialFilters.party &&
      initialFilters.partyEntityId &&
      selectedParty.data?.id === initialFilters.partyEntityId &&
      selectedParty.data.name &&
      !(selectedParty.error instanceof ApiError && [401, 403].includes(selectedParty.error.status))
    )
      setFilters((current) => ({ ...current, party: selectedParty.data?.name ?? "" }));
  }, [initialFilters.party, initialFilters.partyEntityId, selectedParty.data, selectedParty.error, setFilters]);
  function updateFilter<K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setValidationError(null);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    const error = validateDealSearchFilters(filters);
    if (error) {
      setValidationError(error);
      return;
    }
    const sortBy = amountSortFields.has(filters.sortBy) && !filters.currency ? "announced_at" : filters.sortBy;
    onSearchChange({ ...filters, query: filters.query.trim(), party: filters.party.trim(), sortBy }, 0);
  }
  function clearFilters() {
    setFilters(emptyDealSearchFilters);
    setValidationError(null);
    onSearchChange(emptyDealSearchFilters, 0);
  }
  function applyLandscapeFilter(field: DealLandscapeFilterField, value: string) {
    if (value === "__missing__") return;
    if (field === "assetModality") {
      onSearchChange({ ...initialFilters, assetModalities: [value] }, 0);
      return;
    }
    onSearchChange({ ...initialFilters, [field]: value }, 0);
  }
  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "announced_at", direction: "desc" });
    if (!sort.every((criterion) => dealSortFields.includes(criterion.field as DealSearchFilters["sortBy"]))) return;
    const normalized = sort as NonNullable<DealSearchFilters["sort"]>;
    if (normalized.some((criterion) => amountSortFields.has(criterion.field)) && !initialFilters.currency) return;
    onSearchChange(
      { ...initialFilters, sortBy: normalized[0].field, sortDirection: normalized[0].direction, sort: normalized },
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
        filters: initialFilters,
        displayMode,
        analysis: { dimension: analysisDimension, view: analysisView, limit: analysisLimit },
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
  const columns = useDealColumns(initialFilters.currency, onDealChange, openDealEntity);
  const denied = result.error instanceof ApiError && [401, 403].includes(result.error.status),
    data = denied ? undefined : result.data;
  const detailDenied = detail.error instanceof ApiError && [401, 403].includes(detail.error.status);
  const detailMismatch = !detailDenied && detail.data && detail.data.id !== selectedDealId;
  const detailData = detailDenied || detailMismatch ? undefined : detail.data;
  const detailError = detailMismatch
    ? new Error(t("交易详情与请求标识不一致"))
    : detail.error instanceof Error
      ? detail.error
      : null;
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    dealRowId,
    dealEntityId,
  );
  const sorting = tableSortingFromCriteria(initialFilters.sort, initialFilters.sortBy, initialFilters.sortDirection);
  const clearable = hasDealSearchFilter(initialFilters) || hasDealSearchFilter(filters);
  const feedback = dealSaveFeedback(saveFeedback);
  const partyDenied = partySuggestions.error instanceof ApiError && [401, 403].includes(partySuggestions.error.status);
  if (selectedDealId)
    return (
      <>
        <DealProfessionalDossier
          data={detailData}
          loading={detail.isFetching}
          error={detailError}
          activeSection={activeSection}
          onSectionChange={onSectionChange}
          onRetry={() => void detail.refetch()}
          onClose={() => onDealChange(null)}
          onOpenEntity={openDealEntity}
          onOpenProvenance={setProvenanceSelection}
        />
        {provenanceSelection ? (
          <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
        ) : null}
      </>
    );
  return (
    <section className="data-section deal-section">
      <div className="explorer-intro">
        <p>{t("检索交易与关联资产，核对参与方、权益、金额及原始披露。")}</p>
      </div>
      <PublicResearchPanel defaultQuery={initialFilters.query} defaultTopic="disclosures" />
      <DealFilterForm
        filters={filters}
        facets={data?.facets}
        suggestions={partyDenied ? [] : (partySuggestions.data?.items ?? [])}
        suggestionsEnabled={
          !filters.partyEntityId && debouncedParty.length >= 2 && debouncedParty === filters.party.trim()
        }
        suggestionsLoading={partySuggestions.isFetching}
        updateFilter={updateFilter}
        onPartyText={(party) => setFilters((current) => ({ ...current, party, partyEntityId: "" }))}
        chooseParty={(id, name) => {
          setFilters((current) => ({ ...current, party: name, partyEntityId: id }));
          setValidationError(null);
        }}
        submit={submit}
        clearFilters={clearFilters}
        querying={result.isFetching}
        clearable={clearable}
        validationError={validationError ? professionalValidationText(validationError) : ""}
      />
      <AppliedFiltersBar
        filters={data?.applied_filters}
        labels={Object.fromEntries(Object.entries(appliedDealFilterLabels).map(([key, caption]) => [key, t(caption)]))}
        valueLabels={{
          deal_type: localizedDealLabels(dealTypeLabels),
          status: localizedDealLabels(statusLabels),
          direction: localizedDealLabels(directionLabels),
          party_role: localizedDealLabels(partyRoleLabels),
          development_phase_at_transaction: localizedDealLabels(phaseLabels),
          current_development_phase: localizedDealLabels(phaseLabels),
          right_type: localizedDealLabels(rightTypeLabels),
        }}
        onClear={clearFilters}
      />
      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel={t("正在查询交易")}
        refreshingLabel={t("正在刷新交易")}
        fallbackError={t("交易查询失败")}
        onCancel={queryCancellation.cancel}
        onRetry={retryResult}
        onDismissCancellation={queryCancellation.reset}
      >
        {data ? (
          <div className="domain-results">
            <DealResultActions
              data={data}
              displayMode={displayMode}
              refreshing={result.isFetching}
              saveable={hasDealSearchFilter(initialFilters)}
              onRefresh={retryResult}
              onDisplayMode={onDisplayModeChange}
              onSave={() => {
                setSaveName(initialFilters.query.trim() || t("交易情报监控"));
                setSaveFeedback(null);
                save.reset();
                setSaveOpen(true);
              }}
            />
            {data.total && displayMode === "landscape" ? (
              <DealLandscape
                landscape={data.landscape}
                dimension={analysisDimension}
                view={analysisView}
                limit={analysisLimit}
                onFilter={applyLandscapeFilter}
                onAnalysisChange={onAnalysisChange}
              />
            ) : data.items.length ? (
              <VirtualDataTable
                ariaLabel={t("交易结果")}
                columns={columns}
                data={data.items}
                getRowId={dealRowId}
                toolbarActions={
                  <AddToComparisonControl
                    selectedEntityIds={selectedEntityIds}
                    onAdded={(message) => {
                      setSaveFeedback({ kind: "comparison", message });
                      clearSelection();
                    }}
                  />
                }
                rowSelection={{
                  selectedRowIds,
                  onChange: onSelectionChange,
                  getRowLabel: (deal) => t("对比 {name}", { name: deal.name }),
                  label: t("选择对比交易"),
                  maxSelectedRows: 20,
                }}
                preferenceKey="deals"
                totalRows={data.total}
                sorting={sorting}
                onSortingChange={changeSorting}
                sortingScope="all"
                defaultSorting={[{ id: "announced_at", desc: true }]}
              />
            ) : (
              <EmptyQueryResult
                domain={t("交易")}
                filtered={Boolean(data.applied_filters?.length)}
                onClear={clearFilters}
              />
            )}
            {displayMode === "list" ? (
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange(initialFilters, offset)}
                ariaLabel={t("交易结果分页")}
              />
            ) : null}
          </div>
        ) : null}
      </ProfessionalQueryState>
      {feedback && !saveOpen ? (
        <p
          className={saveFeedback?.kind === "error" ? "inline-error" : "inline-feedback"}
          role={saveFeedback?.kind === "error" ? "alert" : "status"}
        >
          {feedback}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel={t("交易")}
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        error={saveFeedback?.kind === "error" ? feedback : ""}
        onNameChange={setSaveName}
        onSharedChange={setSaveShared}
        onMonitorChange={setSaveMonitor}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void submitSavedSearch(event)}
      />
    </section>
  );
}
