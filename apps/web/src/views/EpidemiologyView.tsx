import { useMutation, useQuery } from "@tanstack/react-query";
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
  type EpidemiologyFilters,
  epidemiologyKeys,
  epidemiologySortFields,
  hasEpidemiologySearchFilter,
  loadEpidemiologyTrend,
  saveEpidemiologySearch,
  searchEpidemiology,
} from "../lib/contracts/epidemiology";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { useLocale } from "../lib/i18n";
import { epidemiologyText as t } from "../lib/i18n/epidemiology";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";
import { EpidemiologyFilterForm } from "./epidemiology/EpidemiologyFilterForm";
import { EpidemiologyLandscape } from "./epidemiology/EpidemiologyLandscape";
import { EpidemiologyResultActions } from "./epidemiology/EpidemiologyResultActions";
import { EpidemiologyTrendPanel } from "./epidemiology/EpidemiologyTrendPanel";
import { type TrendSelection, trendMatchesSelection } from "./epidemiology/presentation";
import { type EpidemiologySaveFeedback, epidemiologySaveFeedback } from "./epidemiology/saveFeedback";
import { useEpidemiologyColumns } from "./epidemiology/useEpidemiologyColumns";
import "../styles/epidemiology-research.css";

const PAGE_SIZE = 100;
const appliedFilterLabels = {
  q: "关键词",
  disease_entity_id: "疾病",
  measure: "统计指标",
  geography: "地区",
  unit: "单位",
  patient_population_id: "标准患者人群",
  population_scope: "人群范围",
  age_group: "年龄组",
  sex: "性别",
  period_start_from: "统计周期",
  period_end_to: "统计周期",
} as const;
export function EpidemiologyView({
  initialFilters,
  initialOffset,
  onSearchChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  initialFilters: EpidemiologyFilters;
  initialOffset: number;
  onSearchChange: (filters: EpidemiologyFilters, offset: number) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  useLocale();
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [trendSelection, setTrendSelection] = useState<TrendSelection | null>(null);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveFeedback, setSaveFeedback] = useState<EpidemiologySaveFeedback | null>(null);
  const saveMessage = epidemiologySaveFeedback(saveFeedback);
  const resultQueryKey = epidemiologyKeys.search(initialFilters, initialOffset);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchEpidemiology(initialFilters, initialOffset, signal),
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const trend = useQuery({
    queryKey: epidemiologyKeys.trend(
      trendSelection?.diseaseId ?? "",
      trendSelection?.observationId ?? "",
      trendSelection?.filters ?? initialFilters,
    ),
    queryFn: ({ signal }) =>
      loadEpidemiologyTrend(
        trendSelection?.diseaseId ?? "",
        trendSelection?.observationId ?? "",
        trendSelection?.filters ?? initialFilters,
        signal,
      ),
    enabled: Boolean(trendSelection),
  });
  const save = useMutation({ mutationFn: saveEpidemiologySearch });
  const openEpidemiologyEntity = useCallback<DossierEntityOpener>(
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

  function setFilter<Key extends keyof EpidemiologyFilters>(key: Key, value: EpidemiologyFilters[Key]) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setTrendSelection(null);
    onSearchChange({ ...filters, query: filters.query.trim() }, 0);
  }

  function clearFilters() {
    const cleared: EpidemiologyFilters = {
      query: "",
      displayMode: initialFilters.displayMode,
      analysisView: initialFilters.analysisView,
      diseaseEntityId: "",
      measure: "",
      geography: "",
      unit: "",
      patientPopulationId: "",
      populationScope: "",
      ageGroup: "",
      sex: "",
      periodStartFrom: "",
      periodEndTo: "",
      sortBy: "period_end",
      sortDirection: "desc",
    };
    setFilters(cleared);
    setTrendSelection(null);
    onSearchChange(cleared, 0);
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "period_end", direction: "desc" });
    if (!sort.every((criterion) => epidemiologySortFields.includes(criterion.field as EpidemiologyFilters["sortBy"]))) {
      return;
    }
    const normalizedSort = sort as NonNullable<EpidemiologyFilters["sort"]>;
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

  const columns = useEpidemiologyColumns(openEpidemiologyEntity, setTrendSelection, setProvenanceSelection);

  const resultDenied = result.error instanceof ApiError && [401, 403].includes(result.error.status);
  const data = resultDenied ? undefined : result.data;
  const trendDenied = trend.error instanceof ApiError && [401, 403].includes(trend.error.status);
  const trendMismatch =
    !trendDenied && trend.data && trendSelection && !trendMatchesSelection(trend.data, trendSelection);
  const trendData = trendDenied || trendMismatch ? undefined : trend.data;
  const trendError = trendMismatch ? new Error(t("趋势响应与请求口径不一致")) : trend.error;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const hasFilters = hasEpidemiologySearchFilter(filters);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <section className="data-section epidemiology-section">
      <div className="explorer-intro">
        <p>{t("按疾病、人群、地区、时间和统计口径查询患病、发病、死亡及患者规模数据。")}</p>
      </div>

      <EpidemiologyFilterForm
        filters={filters}
        data={data}
        setFilter={setFilter}
        submit={submit}
        clearFilters={clearFilters}
        querying={result.isFetching}
        hasFilters={hasFilters}
      />

      <AppliedFiltersBar
        filters={data?.applied_filters}
        labels={Object.fromEntries(Object.entries(appliedFilterLabels).map(([key, label]) => [key, t(label)]))}
        onClear={clearFilters}
      />

      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel={t("正在查询流行病学数据")}
        fallbackError={t("流行病学数据加载失败")}
        onCancel={queryCancellation.cancel}
        onRetry={retryResult}
        onDismissCancellation={queryCancellation.reset}
      >
        {data ? (
          <div className="domain-results">
            <EpidemiologyResultActions
              data={data}
              filters={initialFilters}
              refreshing={result.isFetching}
              onRefresh={retryResult}
              onDisplayMode={(displayMode) => onSearchChange({ ...initialFilters, displayMode }, 0)}
              onSave={() => {
                setSaveName(initialFilters.query.trim() || t("疾病负担监控"));
                setSaveFeedback(null);
                save.reset();
                setSaveOpen(true);
              }}
            />
            {initialFilters.displayMode === "landscape" ? (
              <EpidemiologyLandscape
                landscape={data.landscape}
                view={initialFilters.analysisView}
                onViewChange={(analysisView) => onSearchChange({ ...initialFilters, analysisView }, 0)}
                onFilter={(field, value) =>
                  onSearchChange(
                    field === "measure"
                      ? { ...initialFilters, measure: value }
                      : field === "geography"
                        ? { ...initialFilters, geography: value }
                        : { ...initialFilters, populationScope: value },
                    0,
                  )
                }
              />
            ) : data.items.length ? (
              <VirtualDataTable
                ariaLabel={t("流行病学结果")}
                columns={columns}
                data={data.items}
                getRowId={(item) => item.id}
                preferenceKey="epidemiology"
                totalRows={data.total}
                sorting={sorting}
                onSortingChange={changeSorting}
                sortingScope="all"
                defaultSorting={[{ id: "period_end", desc: true }]}
                toolbarActions={<DomainExportControl dataset="epidemiology" totalRows={data.total} />}
              />
            ) : (
              <EmptyQueryResult
                domain={t("流行病学数据")}
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
              ariaLabel={t("流行病学结果分页")}
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
        domainLabel={t("流行病学")}
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

      {trendSelection && !resultDenied ? (
        <EpidemiologyTrendPanel
          selection={trendSelection}
          data={trendData}
          error={trendError}
          loading={trend.isFetching}
          onClose={() => setTrendSelection(null)}
          onRetry={() => void trend.refetch()}
        />
      ) : null}

      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </section>
  );
}
