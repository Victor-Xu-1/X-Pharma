import { useMutation, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { type FormEvent, useCallback, useDeferredValue, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ProfessionalQueryState } from "../components/common";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { PipelineLandscape, type PipelineLandscapeFilterField } from "../components/PipelineLandscape";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  emptyPipelineSearchFilters,
  hasPipelineSearchFilter,
  PIPELINE_PAGE_SIZE,
  type PipelineSearchFilters,
  pipelineKeys,
  pipelineSortFields,
  savePipelineSearch,
  searchPipelines,
} from "../lib/contracts/pipeline";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import type { CompetitiveProgramRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { pipelineText as t } from "../lib/i18n/pipeline";
import { professionalEnumLabel } from "../lib/i18n/professionalEnums";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { localizedDevelopmentPhase, localizedProgramModality } from "../lib/i18n/programVocabulary";
import { compactPhaseLabels as phaseLabels } from "../lib/phasePresentation";
import {
  pipelineBooleanSignalLabels as booleanSignalLabels,
  pipelineResultEvaluationLabels as resultEvaluationLabels,
  validatePipelineSignalFilters,
} from "../lib/pipelineSignals";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import { appliedFilterLabels, programStatusLabels } from "./pipeline/filterLabels";
import { pipelineFilterOptions } from "./pipeline/filterOptions";
import { PipelineAdvancedFilters } from "./pipeline/PipelineAdvancedFilters";
import { PipelinePrimaryFilters } from "./pipeline/PipelinePrimaryFilters";
import { PipelineResultActions } from "./pipeline/PipelineResultActions";
import { PipelineSignalFilters } from "./pipeline/PipelineSignalFilters";
import { organizationRoleLabels } from "./pipeline/ProgramCells";
import { type PipelineFeedback, pipelineSaveFeedback } from "./pipeline/saveFeedback";
import { usePipelineColumns } from "./pipeline/usePipelineColumns";
import type { PipelineViewProps } from "./pipeline/viewTypes";

const pipelineRowId = (program: CompetitiveProgramRead) => program.id;
const pipelineEntityId = (program: CompetitiveProgramRead) => program.drug_entity_id;
const defaultPipelineSorting: SortingState = [{ id: "status_date", desc: true }];
export function PipelineView({
  displayMode,
  resultGrain,
  analysisDimension,
  analysisView,
  analysisLimit,
  analysisStageScope,
  targetAggregation,
  initialFilters,
  onSearchChange,
  onDisplayModeChange,
  onResultGrainChange,
  onAnalysisChange,
  onOpenDrug,
  onOpenEntity,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onOpenTrialsForDrug,
  onOpenDealsForDrug,
}: PipelineViewProps) {
  useLocale();
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [entityValueLabels, setEntityValueLabels] = useState<Record<string, Record<string, string>>>({});
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState<PipelineFeedback>("");
  const [filterError, setFilterError] = useState("");
  const analysis = { limit: analysisLimit, stageScope: analysisStageScope, targetAggregation };
  const resultQueryKey = pipelineKeys.search(initialFilters, analysis, resultGrain);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchPipelines(initialFilters, analysis, signal, resultGrain),
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const save = useMutation({ mutationFn: savePipelineSearch });

  function updateFilter<Key extends keyof PipelineSearchFilters>(key: Key, value: PipelineSearchFilters[Key]) {
    setFilterError("");
    setFilters((current) => ({ ...current, [key]: value }));
  }

  const rememberEntity = useCallback((field: string, entityId: string, displayName?: string) => {
    if (!entityId || !displayName) return;
    setEntityValueLabels((current) => {
      if (current[field]?.[entityId] === displayName) return current;
      return { ...current, [field]: { ...current[field], [entityId]: displayName } };
    });
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    const signalError = validatePipelineSignalFilters(filters);
    if (signalError) {
      setFilterError(signalError);
      return;
    }
    setFilterError("");
    onSearchChange({ ...filters, query: filters.query.trim(), offset: 0 });
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        filters: initialFilters,
        analysis: {
          ...analysis,
          dimension: analysisDimension,
          view: analysisView,
        },
        displayMode,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome);
    } catch (error) {
      setSaveMessage({ kind: "failed", reason: error instanceof Error ? error.message : null });
    }
  }

  function clearFilters() {
    const empty = emptyPipelineSearchFilters();
    setFilters(empty);
    setEntityValueLabels({});
    setFilterError("");
    onSearchChange(empty);
  }

  function applyLandscapeFilter(field: PipelineLandscapeFilterField, value: string, label?: string) {
    if (value === "__missing__") return;
    if (field === "targetCombinationKey" && label) rememberEntity("target_combination_key", value, label);
    if (field === "modality") {
      // Modality is a multi-select condition: a landscape drill focuses on that single
      // bucket, expressed as a single-element set.
      onSearchChange({ ...initialFilters, modalities: [value], offset: 0 });
      return;
    }
    onSearchChange({ ...initialFilters, [field]: value, offset: 0 });
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "status_date", direction: "desc" });
    if (!sort.every((criterion) => pipelineSortFields.includes(criterion.field as PipelineSearchFilters["sortBy"]))) {
      return;
    }
    const normalizedSort = sort as NonNullable<PipelineSearchFilters["sort"]>;
    onSearchChange({
      ...initialFilters,
      sortBy: normalizedSort[0].field,
      sortDirection: normalizedSort[0].direction,
      sort: normalizedSort,
      offset: 0,
    });
  }

  // Keep the filter surface responsive while a large real result page is reconciled.
  // The query remains authoritative; only its React presentation is deferred.
  const data = useDeferredValue(result.data);
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    pipelineRowId,
    pipelineEntityId,
  );
  const hasFilters = hasPipelineSearchFilter(initialFilters) || hasPipelineSearchFilter(filters);
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }
  const columns = usePipelineColumns({
    onOpenDealsForDrug,
    onOpenDrug,
    openOrganization,
    openTarget,
    openDisease,
    onOpenTrialsForDrug,
    resultGrain,
  });
  const { modalities } = pipelineFilterOptions(data, filters);
  const entityValueMap = {
    program_status: Object.fromEntries(
      Object.entries(programStatusLabels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
    ),
    modality: Object.fromEntries(modalities.map((value) => [value, localizedProgramModality(value)])),
    drug_entity_id: entityValueLabels.drug_entity_id ?? {},
    target_entity_id: entityValueLabels.target_entity_id ?? {},
    target_combination_key: entityValueLabels.target_combination_key ?? {},
    disease_entity_id: entityValueLabels.disease_entity_id ?? {},
    organization_entity_id: entityValueLabels.organization_entity_id ?? {},
    organization_role: Object.fromEntries(
      Object.entries(organizationRoleLabels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
    ),
    phase: Object.fromEntries(Object.keys(phaseLabels).map((code) => [code, localizedDevelopmentPhase(code)])),
    global_phase: Object.fromEntries(Object.keys(phaseLabels).map((code) => [code, localizedDevelopmentPhase(code)])),
    china_phase: Object.fromEntries(Object.keys(phaseLabels).map((code) => [code, localizedDevelopmentPhase(code)])),
    has_clinical_results: Object.fromEntries(
      Object.entries(booleanSignalLabels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
    ),
    clinical_result_evaluation: Object.fromEntries(
      Object.entries(resultEvaluationLabels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
    ),
    has_deal: Object.fromEntries(
      Object.entries(booleanSignalLabels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
    ),
  };

  return (
    <section className="data-section pipeline-section">
      <div className="explorer-intro">
        <p>{t("按药品、靶点、适应症、研发机构、全球与中国阶段、权益地区及里程碑组合查询。")}</p>
      </div>

      <form className="domain-filter-bar pipeline-filter-bar" onSubmit={submit} aria-label={t("药物与管线筛选")}>
        <PipelinePrimaryFilters
          filters={filters}
          updateFilter={updateFilter}
          data={data}
          rememberEntity={rememberEntity}
        />
        <PipelineAdvancedFilters filters={filters} updateFilter={updateFilter} data={data} />
        <PipelineSignalFilters
          filters={filters}
          updateFilter={updateFilter}
          data={data}
          onSignalsChange={(changes) => {
            setFilters((current) => ({ ...current, ...changes }));
            setFilterError("");
          }}
        />
        {filterError ? (
          <p className="form-error pipeline-filter-error" role="alert">
            {professionalValidationText(filterError)}
          </p>
        ) : null}

        <div className="domain-filter-actions pipeline-filter-actions">
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
        labels={Object.fromEntries(Object.entries(appliedFilterLabels).map(([field, caption]) => [field, t(caption)]))}
        valueLabels={entityValueMap}
        onClear={clearFilters}
      />

      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel={t("正在查询研发管线")}
        refreshingLabel={t("正在刷新研发管线")}
        fallbackError={t("管线查询失败")}
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
                unit={resultGrain === "drug" ? t("个药物") : t("条研发项目")}
                queriedAt={data.as_of}
                showRange={displayMode === "list"}
                note={
                  resultGrain === "drug" && data.project_total !== undefined
                    ? t("覆盖 {count} 条研发项目", { count: data.project_total })
                    : undefined
                }
              />
              <PipelineResultActions
                refreshing={result.isFetching}
                onRefresh={retryResult}
                resultGrain={resultGrain}
                onResultGrainChange={onResultGrainChange}
                displayMode={displayMode}
                onDisplayModeChange={onDisplayModeChange}
                initialFilters={initialFilters}
                totalRows={data.total}
                onSave={() => {
                  setSaveName(initialFilters.query.trim() || t("管线情报监控"));
                  setSaveMessage("");
                  save.reset();
                  setSaveOpen(true);
                }}
              />
            </div>
            {data.total && displayMode === "landscape" ? (
              <PipelineLandscape
                landscape={data.landscape}
                dimension={analysisDimension}
                view={analysisView}
                limit={analysisLimit}
                stageScope={analysisStageScope}
                targetAggregation={targetAggregation}
                onFilter={applyLandscapeFilter}
                onOpenEntity={onOpenEntity}
                onOpenTarget={openTarget}
                onOpenDisease={openDisease}
                onOpenOrganization={openOrganization}
                onAnalysisChange={onAnalysisChange}
              />
            ) : data.items.length ? (
              <VirtualDataTable
                ariaLabel={t("药物与研发管线结果")}
                columns={columns}
                data={data.items}
                getRowId={(program) => program.id}
                preferenceKey="pipeline"
                totalRows={data.total}
                sorting={sorting}
                defaultSorting={defaultPipelineSorting}
                onSortingChange={changeSorting}
                sortingScope="all"
                toolbarActions={
                  <AddToComparisonControl
                    selectedEntityIds={selectedEntityIds}
                    onAdded={(message) => {
                      setSaveMessage(message);
                      clearSelection();
                    }}
                  />
                }
                rowSelection={{
                  selectedRowIds,
                  onChange: onSelectionChange,
                  getRowLabel: (program) => t("对比 {name}", { name: program.drug_name }),
                  label: t("选择对比药物"),
                  maxSelectedRows: 20,
                }}
              />
            ) : (
              <EmptyQueryResult
                domain={t("管线数据")}
                filtered={Boolean(data.applied_filters?.length)}
                onClear={clearFilters}
              />
            )}
            {displayMode === "list" ? (
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PIPELINE_PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange({ ...initialFilters, offset })}
                ariaLabel={t("药物管线结果分页")}
              />
            ) : (
              <footer className="pipeline-landscape-footer">
                <span>{publicCoverageNotice(data.warnings)}</span>
              </footer>
            )}
          </div>
        ) : null}
      </ProfessionalQueryState>
      {saveMessage && !saveOpen ? (
        <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
          {pipelineSaveFeedback(saveMessage)}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel={t("管线")}
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        error={save.isError ? pipelineSaveFeedback(saveMessage) : ""}
        onNameChange={setSaveName}
        onSharedChange={setSaveShared}
        onMonitorChange={setSaveMonitor}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void submitSavedSearch(event)}
      />
    </section>
  );
}
