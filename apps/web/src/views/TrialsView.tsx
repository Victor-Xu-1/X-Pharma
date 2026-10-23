import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ProfessionalQueryState } from "../components/common";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import type { SortingState } from "../components/VirtualDataTable";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { type SortCriterion, sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import {
  hasTrialSearchFilter,
  saveClinicalTrialSearch,
  type TrialSavedSearchInput,
  type TrialSortField,
  trialSortFields,
} from "../lib/contracts/trials";
import type { ClinicalTrialSearchItemRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { clinicalText as t } from "../lib/i18n/clinical";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import { useTrialAppliedLabels } from "./trials/appliedLabels";
import { emptyTrialFilterConditions, emptyTrialSearchInput } from "./trials/emptyInput";
import { type ClinicalFeedback, clinicalSaveFeedback } from "./trials/saveFeedback";
import { TrialCombinationFilters } from "./trials/TrialCombinationFilters";
import { TrialDesignFilters } from "./trials/TrialDesignFilters";
import { TrialLinkedProgramFilters } from "./trials/TrialLinkedProgramFilters";
import { TrialPrimaryFilters } from "./trials/TrialPrimaryFilters";
import { TrialProfessionalDossier } from "./trials/TrialProfessionalDossier";
import { TrialResultFilters } from "./trials/TrialResultFilters";
import { TrialSearchResults } from "./trials/TrialSearchResults";
import { useTrialColumns } from "./trials/useTrialColumns";
import { type TrialFilterConditions, useTrialFilterDraft } from "./trials/useTrialFilterDraft";
import { useTrialQueries } from "./trials/useTrialQueries";
import type { TrialEntityOpener, TrialsViewProps } from "./trials/viewTypes";

const trialRowId = (trial: ClinicalTrialSearchItemRead) => trial.id;
const trialEntityId = (trial: ClinicalTrialSearchItemRead) => trial.entity_id;
export function TrialsView({
  displayMode,
  analysisView,
  initialQuery,
  initialRegistry,
  initialStatus,
  initialPhase,
  initialStudyType,
  initialAcronym,
  initialInitiationType,
  initialTherapyLine,
  initialHasResults,
  initialResultEvaluation,
  initialResultsPostedFrom,
  initialResultsPostedTo,
  initialInvestigationalDrug,
  initialCombinationDrug,
  initialInvestigationalTarget,
  initialCombinationTarget,
  initialInvestigationalDrugEntityIds,
  initialCombinationDrugEntityIds,
  initialInvestigationalTargetEntityIds,
  initialCombinationTargetEntityIds,
  initialLinkedDrugModalities,
  initialLinkedDrugInnovationTypes,
  initialLinkedDrugCategories,
  initialLinkedDrugProgramTags,
  initialLinkedDrugGlobalPhase,
  initialLinkedDrugOrganizationCountryRegion,
  initialRoleEntityId,
  initialRoleEntityIds,
  initialRoleEntityRole,
  initialHasKeyResult,
  initialPublicationId,
  initialConference,
  initialDisclosedFrom,
  initialDisclosedTo,
  initialSortBy,
  initialSortDirection,
  initialSort,
  initialOffset,
  selectedTrialId,
  activeSection,
  onSearchChange,
  onTrialChange,
  onSectionChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onDisplayModeChange,
  onAnalysisViewChange,
  showListReturn = true,
}: TrialsViewProps) {
  useLocale();
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openTrialEntity = useCallback<TrialEntityOpener>(
    (entityType, entityId) => {
      switch (entityType) {
        case "drug":
          openDrug(entityId);
          return;
        case "target":
          openTarget(entityId);
          return;
        case "disease":
          openDisease(entityId);
          return;
        case "organization":
          openOrganization(entityId);
          return;
        default:
          onOpenEntity(entityId);
      }
    },
    [onOpenEntity, openDisease, openDrug, openOrganization, openTarget],
  );
  const appliedConditions: TrialFilterConditions = {
    query: initialQuery,
    registry: initialRegistry,
    status: initialStatus,
    phase: initialPhase,
    studyType: initialStudyType,
    acronym: initialAcronym,
    initiationType: initialInitiationType,
    therapyLine: initialTherapyLine,
    hasResults: initialHasResults,
    resultEvaluation: initialResultEvaluation,
    resultsPostedFrom: initialResultsPostedFrom,
    resultsPostedTo: initialResultsPostedTo,
    investigationalDrug: initialInvestigationalDrug,
    combinationDrug: initialCombinationDrug,
    investigationalTarget: initialInvestigationalTarget,
    combinationTarget: initialCombinationTarget,
    investigationalDrugEntityIds: initialInvestigationalDrugEntityIds,
    combinationDrugEntityIds: initialCombinationDrugEntityIds,
    investigationalTargetEntityIds: initialInvestigationalTargetEntityIds,
    combinationTargetEntityIds: initialCombinationTargetEntityIds,
    linkedDrugModalities: initialLinkedDrugModalities,
    linkedDrugInnovationTypes: initialLinkedDrugInnovationTypes,
    linkedDrugCategories: initialLinkedDrugCategories,
    linkedDrugProgramTags: initialLinkedDrugProgramTags,
    linkedDrugGlobalPhase: initialLinkedDrugGlobalPhase,
    linkedDrugOrganizationCountryRegion: initialLinkedDrugOrganizationCountryRegion,
    roleEntityId: initialRoleEntityId,
    roleEntityIds: initialRoleEntityIds,
    roleEntityRole: initialRoleEntityRole,
    hasKeyResult: initialHasKeyResult,
    publicationId: initialPublicationId,
    conference: initialConference,
    disclosedFrom: initialDisclosedFrom,
    disclosedTo: initialDisclosedTo,
  };
  const { filters, setFilters, setters } = useTrialFilterDraft(appliedConditions);
  const {
    query,
    acronym,
    investigationalDrug,
    combinationDrug,
    investigationalTarget,
    combinationTarget,
    publicationId,
    conference,
  } = filters;

  const appliedSearchInput: TrialSavedSearchInput = {
    ...appliedConditions,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };
  const draftSearchInput: TrialSavedSearchInput = {
    ...filters,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };

  const [linkedProgramFiltersOpen, setLinkedProgramFiltersOpen] = useState(
    Boolean(
      initialLinkedDrugModalities.length ||
        initialLinkedDrugInnovationTypes.length ||
        initialLinkedDrugCategories.length ||
        initialLinkedDrugProgramTags.length ||
        initialLinkedDrugGlobalPhase ||
        initialLinkedDrugOrganizationCountryRegion,
    ),
  );

  const [roleEntityLabels, setRoleEntityLabels] = useState<Record<string, string>>({});

  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState<ClinicalFeedback>("");

  const hasAppliedLinkedFilters = Boolean(
    initialLinkedDrugModalities.length ||
      initialLinkedDrugInnovationTypes.length ||
      initialLinkedDrugCategories.length ||
      initialLinkedDrugProgramTags.length ||
      initialLinkedDrugGlobalPhase ||
      initialLinkedDrugOrganizationCountryRegion,
  );
  useEffect(() => {
    if (hasAppliedLinkedFilters) setLinkedProgramFiltersOpen(true);
  }, [hasAppliedLinkedFilters]);
  const { resultQueryKey, result, detail, resultData, detailData } = useTrialQueries(
    appliedSearchInput,
    initialOffset,
    selectedTrialId,
  );
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const save = useMutation({ mutationFn: saveClinicalTrialSearch });

  function rememberRoleEntity(entityId: string, displayName?: string) {
    if (!entityId || !displayName) return;
    setRoleEntityLabels((current) =>
      current[entityId] === displayName ? current : { ...current, [entityId]: displayName },
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearchChange({
      ...draftSearchInput,
      query: query.trim(),
      acronym: acronym.trim(),
      investigationalDrug: investigationalDrug.trim(),
      combinationDrug: combinationDrug.trim(),
      investigationalTarget: investigationalTarget.trim(),
      combinationTarget: combinationTarget.trim(),
      publicationId: publicationId.trim(),
      conference: conference.trim(),
      offset: 0,
    });
  }

  function clearFilters() {
    setFilters(emptyTrialFilterConditions);
    setLinkedProgramFiltersOpen(false);
    setRoleEntityLabels({});
    onSearchChange({
      ...emptyTrialSearchInput,
      sortBy: initialSortBy,
      sortDirection: initialSortDirection,
      sort: initialSort,
      displayMode,
      analysisView,
      offset: 0,
    });
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
      setSaveMessage(outcome);
    } catch (error) {
      setSaveMessage({ kind: "failed", reason: error instanceof Error ? error.message : null });
    }
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "last_update_posted", direction: "desc" });
    if (!sort.every((criterion) => trialSortFields.includes(criterion.field as TrialSortField))) return;
    const normalizedSort = sort as SortCriterion<TrialSortField>[];
    onSearchChange({
      ...appliedSearchInput,
      sortBy: normalizedSort[0].field,
      sortDirection: normalizedSort[0].direction,
      sort: normalizedSort,
      offset: 0,
    });
  }

  function changePage(offset: number) {
    onSearchChange({ ...appliedSearchInput, offset });
  }

  function applyLandscapeFilter(field: "phase" | "result_evaluation", value: string) {
    onSearchChange({
      ...appliedSearchInput,
      phase: field === "phase" ? value : initialPhase,
      resultEvaluation: field === "result_evaluation" ? value : initialResultEvaluation,
      offset: 0,
    });
  }

  const columns = useTrialColumns(openTrialEntity, onTrialChange);
  const data = resultData;
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    trialRowId,
    trialEntityId,
  );
  const { labels: appliedLabels, valueLabels: appliedValueLabels } = useTrialAppliedLabels(
    appliedConditions,
    roleEntityLabels,
  );
  const sorting: SortingState = tableSortingFromCriteria(initialSort, initialSortBy, initialSortDirection);
  const hasFilters = hasTrialSearchFilter(appliedSearchInput) || hasTrialSearchFilter(draftSearchInput);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  if (selectedTrialId) {
    return (
      <>
        <TrialProfessionalDossier
          trialId={selectedTrialId}
          data={detailData}
          loading={detail.isLoading}
          error={detail.error}
          activeSection={activeSection}
          onRetry={() => void detail.refetch()}
          onBack={showListReturn ? () => onTrialChange(null) : undefined}
          onSectionChange={onSectionChange}
          onOpenTrialEntity={openTrialEntity}
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
      <section className="data-section trial-section">
        <div className="explorer-intro">
          <p>{t("聚合注册平台的试验设计、状态、分期、适应症、干预和申办方，并关联药物与靶点信息。")}</p>
          <p>{t("注册干预列表不自动区分主药与联合用药；角色条件只匹配有明确角色证据的记录。")}</p>
        </div>

        <form className="domain-filter-bar trial-filter-bar" onSubmit={submit} aria-label={t("临床试验筛选")}>
          <TrialPrimaryFilters
            filters={filters}
            setters={setters}
            data={data}
            rememberRoleEntity={rememberRoleEntity}
          />
          <TrialDesignFilters filters={filters} setters={setters} data={data} rememberRoleEntity={rememberRoleEntity} />
          <TrialCombinationFilters
            filters={filters}
            setters={setters}
            data={data}
            rememberRoleEntity={rememberRoleEntity}
          />
          <TrialLinkedProgramFilters
            filters={filters}
            setters={setters}
            data={data}
            rememberRoleEntity={rememberRoleEntity}
            linkedProgramFiltersOpen={linkedProgramFiltersOpen}
            setLinkedProgramFiltersOpen={setLinkedProgramFiltersOpen}
          />
          <TrialResultFilters filters={filters} setters={setters} data={data} rememberRoleEntity={rememberRoleEntity} />
          <div className="domain-filter-actions">
            <button className="primary-button" type="submit" disabled={result.isFetching}>
              <Search size={16} />
              {t("查询")}
            </button>
            <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
              {t("清除")}
            </button>
          </div>
        </form>

        <AppliedFiltersBar
          filters={data?.applied_filters}
          labels={appliedLabels}
          valueLabels={appliedValueLabels}
          onClear={clearFilters}
        />

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          refreshingLabel={t("正在刷新临床试验")}
          loadingLabel={t("正在查询临床试验")}
          fallbackError={t("临床试验查询失败")}
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <TrialSearchResults
              data={data}
              refreshing={result.isFetching}
              onRefresh={retryResult}
              input={appliedSearchInput}
              displayMode={displayMode}
              analysisView={analysisView}
              onDisplayModeChange={onDisplayModeChange}
              onAnalysisViewChange={onAnalysisViewChange}
              onSave={() => {
                setSaveName(initialQuery.trim() || t("临床试验情报监控"));
                setSaveMessage("");
                save.reset();
                setSaveOpen(true);
              }}
              onLandscapeFilter={applyLandscapeFilter}
              columns={columns}
              sorting={sorting}
              onSortingChange={changeSorting}
              selectedRowIds={selectedRowIds}
              selectedEntityIds={selectedEntityIds}
              onSelectionChange={onSelectionChange}
              onComparisonAdded={(message) => {
                setSaveMessage(message);
                clearSelection();
              }}
              onClear={clearFilters}
              onPageChange={changePage}
            />
          ) : null}
        </ProfessionalQueryState>
      </section>
      {saveMessage && !saveOpen ? (
        <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
          {clinicalSaveFeedback(saveMessage)}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel={t("临床试验")}
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        error={save.isError ? clinicalSaveFeedback(saveMessage) : ""}
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
