import { useMutation, useQuery } from "@tanstack/react-query";
import { BookmarkPlus, Search, TrendingUp, X } from "lucide-react";
import { type FormEvent, lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";

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
import { SecondaryFilters } from "../components/SecondaryFilters";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  type EpidemiologyFilters,
  type EpidemiologyObservation,
  epidemiologyKeys,
  hasEpidemiologySearchFilter,
  loadEpidemiologyTrend,
  saveEpidemiologySearch,
  searchEpidemiology,
} from "../lib/contracts/epidemiology";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import { epidemiologyMeasureLabels } from "../lib/epidemiologyDisplay";
import { facetOptions } from "../lib/facets";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DossierEntityOpener } from "./EntityDossierView";

const PAGE_SIZE = 100;
const epidemiologySortFields: EpidemiologyFilters["sortBy"][] = [
  "period_end",
  "period_start",
  "disease",
  "measure",
  "value",
  "geography",
  "unit",
  "publisher",
  "sample_size",
];
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
const TrendLineChart = lazy(() =>
  import("../components/TrendLineChart").then((module) => ({ default: module.TrendLineChart })),
);

const measureOrder = Object.keys(epidemiologyMeasureLabels);

type TrendSelection = {
  observationId: string;
  diseaseId: string;
  diseaseName: string;
  filters: EpidemiologyFilters;
};

function formatNumber(value: number | null) {
  if (value === null) return "--";
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value);
}

function estimateLabel(item: EpidemiologyObservation) {
  const interval =
    item.lower_bound !== null || item.upper_bound !== null
      ? ` (${formatNumber(item.lower_bound)}-${formatNumber(item.upper_bound)})`
      : "";
  return `${formatNumber(item.value)}${interval}`;
}

function periodLabel(item: EpidemiologyObservation) {
  if (!item.period_start && !item.period_end) return "未标注";
  if (item.period_start === item.period_end) return formatDate(item.period_start ?? "");
  return `${formatDate(item.period_start ?? "")} - ${formatDate(item.period_end ?? "")}`;
}

function comparableTrend(item: EpidemiologyObservation): TrendSelection {
  return {
    observationId: item.id,
    diseaseId: item.disease_entity.id,
    diseaseName: item.disease_entity.name,
    filters: {
      query: "",
      displayMode: "list" as const,
      analysisView: "chart" as const,
      diseaseEntityId: item.disease_entity.id,
      measure: item.measure,
      geography: item.geography,
      unit: item.unit,
      patientPopulationId: item.patient_population_id ?? "",
      populationScope: item.population_scope,
      ageGroup: item.age_group ?? "",
      sex: item.sex ?? "",
      periodStartFrom: "",
      periodEndTo: "",
      sortBy: "period_end",
      sortDirection: "desc",
    },
  };
}

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
  const [filters, setFilters] = useState(initialFilters);
  const [trendSelection, setTrendSelection] = useState<TrendSelection | null>(null);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const {
    query: initialQuery,
    diseaseEntityId: initialDiseaseEntityId,
    measure: initialMeasure,
    geography: initialGeography,
    unit: initialUnit,
    patientPopulationId: initialPatientPopulationId,
    populationScope: initialPopulationScope,
    ageGroup: initialAgeGroup,
    sex: initialSex,
    periodStartFrom: initialPeriodStartFrom,
    periodEndTo: initialPeriodEndTo,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    displayMode: initialDisplayMode,
    analysisView: initialAnalysisView,
  } = initialFilters;
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

  useEffect(
    () =>
      setFilters({
        query: initialQuery,
        displayMode: initialDisplayMode,
        analysisView: initialAnalysisView,
        diseaseEntityId: initialDiseaseEntityId,
        measure: initialMeasure,
        geography: initialGeography,
        unit: initialUnit,
        patientPopulationId: initialPatientPopulationId,
        populationScope: initialPopulationScope,
        ageGroup: initialAgeGroup,
        sex: initialSex,
        periodStartFrom: initialPeriodStartFrom,
        periodEndTo: initialPeriodEndTo,
        sortBy: initialSortBy,
        sortDirection: initialSortDirection,
      }),
    [
      initialQuery,
      initialDiseaseEntityId,
      initialMeasure,
      initialGeography,
      initialUnit,
      initialPatientPopulationId,
      initialPopulationScope,
      initialAgeGroup,
      initialSex,
      initialPeriodStartFrom,
      initialPeriodEndTo,
      initialSortBy,
      initialSortDirection,
      initialDisplayMode,
      initialAnalysisView,
    ],
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
      displayMode: initialDisplayMode,
      analysisView: initialAnalysisView,
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
      setSaveMessage(error instanceof Error ? error.message : "流行病学检索保存失败");
    }
  }

  const columns = useMemo<ColumnDef<EpidemiologyObservation, unknown>[]>(
    () => [
      {
        id: "disease",
        accessorFn: (row) => row.disease_entity.name,
        header: "疾病 / 人群",
        size: 210,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            aria-label={row.original.disease_entity.name}
            onClick={() => openEpidemiologyEntity("disease", row.original.disease_entity.id)}
          >
            <strong>{row.original.disease_entity.name}</strong>
            <small
              className="cell-subtitle"
              title={row.original.patient_population?.target_entities.map((entity) => entity.name).join(", ")}
            >
              {row.original.patient_population?.name ?? row.original.population_scope}
            </small>
            {row.original.patient_population ? (
              <small className="cell-subtitle">统计口径：{row.original.population_scope}</small>
            ) : null}
          </button>
        ),
      },
      {
        id: "value",
        accessorFn: (row) => row.value,
        header: "指标 / 估计值",
        size: 175,
        cell: ({ row }) => (
          <span className="domain-primary-cell epidemiology-estimate">
            <StatusBadge value={epidemiologyMeasureLabels[row.original.measure] ?? row.original.measure} />
            <strong>{estimateLabel(row.original)}</strong>
            <small>{row.original.unit}</small>
          </span>
        ),
      },
      {
        accessorKey: "geography",
        header: "地区",
        size: 120,
      },
      {
        id: "demographic",
        header: "年龄 / 性别",
        size: 120,
        enableSorting: false,
        cell: ({ row }) => `${row.original.age_group ?? "全部"} / ${row.original.sex ?? "全部"}`,
      },
      {
        id: "period_end",
        accessorFn: (row) => row.period_end,
        header: "观察期",
        size: 165,
        cell: ({ row }) => periodLabel(row.original),
      },
      {
        id: "publisher",
        accessorFn: (row) => row.publisher_entity?.name ?? null,
        header: "发布机构",
        size: 145,
        cell: ({ row }) =>
          row.original.publisher_entity ? (
            <button
              className="table-link-button"
              type="button"
              onClick={() =>
                openEpidemiologyEntity(
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
        accessorKey: "methodology",
        header: "方法学",
        size: 220,
        enableSorting: false,
        cell: ({ getValue }) => <span className="methodology-cell">{String(getValue() ?? "未标注")}</span>,
      },
      {
        id: "actions",
        header: "操作",
        size: 86,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-icon-actions">
            <button
              className="icon-button"
              type="button"
              title="查看同口径趋势"
              aria-label={`查看 ${row.original.disease_entity.name} 同口径趋势`}
              onClick={() => setTrendSelection(comparableTrend(row.original))}
            >
              <TrendingUp size={16} />
            </button>
            <ProvenanceButton
              selection={{
                resourceType: "epidemiology_observation",
                resourceId: row.original.id,
                label: `${row.original.disease_entity.name} ${epidemiologyMeasureLabels[row.original.measure] ?? row.original.measure}`,
              }}
              onOpen={setProvenanceSelection}
            />
          </span>
        ),
      },
    ],
    [openEpidemiologyEntity],
  );

  const data = result.data;
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const measureOptions = Array.from(
    new Set([...measureOrder, ...facetOptions(data?.facets, "measure", filters.measure)]),
  );
  const geographyOptions = facetOptions(data?.facets, "geography", filters.geography);
  const unitOptions = facetOptions(data?.facets, "unit", filters.unit);
  const patientPopulationOptions = data?.patient_populations ?? [];
  const populationOptions = facetOptions(data?.facets, "population_scope", filters.populationScope);
  const ageOptions = facetOptions(data?.facets, "age_group", filters.ageGroup);
  const sexOptions = facetOptions(data?.facets, "sex", filters.sex);
  const pageStart = data?.total ? data.offset + 1 : 0;
  const pageEnd = data ? Math.min(data.offset + data.items.length, data.total) : 0;
  const hasFilters = Object.values(initialFilters).some(Boolean);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  return (
    <section className="data-section epidemiology-section">
      <div className="explorer-intro">
        <p>按疾病、人群、地区、时间和统计口径查询患病、发病、死亡及患者规模数据。</p>
      </div>

      <form className="domain-filter-bar epidemiology-filter-bar" onSubmit={submit} aria-label="流行病学筛选">
        <EntityFilterSelect
          label="疾病"
          entityType="disease"
          value={filters.diseaseEntityId}
          onChange={(entityId) => setFilter("diseaseEntityId", entityId)}
          placeholder="输入疾病名称或别名"
        />
        <label className="domain-query-field">
          <span>来源或方法</span>
          <span className="input-with-icon">
            <Search size={16} />
            <input
              value={filters.query}
              onChange={(event) => setFilter("query", event.target.value)}
              placeholder="发布机构、方法学或观测编号"
              maxLength={500}
            />
          </span>
        </label>
        <label>
          <span>统计指标</span>
          <select value={filters.measure} onChange={(event) => setFilter("measure", event.target.value)}>
            <option value="">全部</option>
            {measureOptions.map((value) => (
              <option value={value} key={value}>
                {epidemiologyMeasureLabels[value] ?? value} ({data?.facets?.measure?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>地区</span>
          <select value={filters.geography} onChange={(event) => setFilter("geography", event.target.value)}>
            <option value="">全部</option>
            {geographyOptions.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.geography?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <SecondaryFilters
          activeCount={
            [
              filters.unit,
              filters.patientPopulationId,
              filters.populationScope,
              filters.ageGroup,
              filters.sex,
              filters.periodStartFrom,
              filters.periodEndTo,
            ].filter(Boolean).length
          }
        >
          <label>
            <span>单位</span>
            <select value={filters.unit} onChange={(event) => setFilter("unit", event.target.value)}>
              <option value="">全部</option>
              {unitOptions.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.unit?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>标准患者人群</span>
            <select
              value={filters.patientPopulationId}
              onChange={(event) => setFilter("patientPopulationId", event.target.value)}
            >
              <option value="">全部</option>
              {patientPopulationOptions.map((option) => (
                <option value={option.id} key={option.id}>
                  {option.name} ({option.count})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>人群口径</span>
            <select
              value={filters.populationScope}
              onChange={(event) => setFilter("populationScope", event.target.value)}
            >
              <option value="">全部</option>
              {populationOptions.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.population_scope?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>年龄组</span>
            <select value={filters.ageGroup} onChange={(event) => setFilter("ageGroup", event.target.value)}>
              <option value="">全部</option>
              {ageOptions.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.age_group?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>性别</span>
            <select value={filters.sex} onChange={(event) => setFilter("sex", event.target.value)}>
              <option value="">全部</option>
              {sexOptions.map((value) => (
                <option value={value} key={value}>
                  {value} ({data?.facets?.sex?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>观察期起</span>
            <input
              type="date"
              value={filters.periodStartFrom}
              onChange={(event) => setFilter("periodStartFrom", event.target.value)}
            />
          </label>
          <label>
            <span>观察期止</span>
            <input
              type="date"
              value={filters.periodEndTo}
              min={filters.periodStartFrom || undefined}
              onChange={(event) => setFilter("periodEndTo", event.target.value)}
            />
          </label>
        </SecondaryFilters>
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

      <AppliedFiltersBar filters={data?.applied_filters} labels={appliedFilterLabels} onClear={clearFilters} />

      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel="正在查询流行病学数据"
        fallbackError="流行病学数据加载失败"
        onCancel={queryCancellation.cancel}
        onRetry={retryResult}
        onDismissCancellation={queryCancellation.reset}
      >
        {data ? (
          <div className="domain-results">
            <div className="pipeline-result-toolbar">
              <div className="result-summary">
                <strong>{data.total}</strong>
                <span>项疾病负担观测</span>
                <small>
                  {pageStart}-{pageEnd} · 截止 {formatDate(data.as_of, true)}
                </small>
              </div>
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
                  disabled={!hasEpidemiologySearchFilter(initialFilters)}
                  title={
                    hasEpidemiologySearchFilter(initialFilters) ? "保存或订阅当前流行病学查询" : "至少应用一个查询条件"
                  }
                  onClick={() => {
                    setSaveName(initialFilters.query.trim() || "疾病负担监控");
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
              <DomainLandscape<"measure" | "geography" | "population_scope">
                domainId="epidemiology"
                ariaLabel="疾病负担统计分析"
                total={data.landscape.total_observations}
                totalUnit="条观察"
                unitLabel="观察数"
                sections={[
                  {
                    id: "measure",
                    title: "统计口径",
                    detail: "按统计口径统计完整命中集",
                    buckets: data.landscape.measure ?? [],
                    filterField: "measure",
                  },
                  {
                    id: "geography",
                    title: "地区",
                    detail: "按结果口径地区统计完整命中集",
                    buckets: data.landscape.geography ?? [],
                    filterField: "geography",
                  },
                  {
                    id: "population-scope",
                    title: "人群口径",
                    detail: "按人群口径统计完整命中集",
                    buckets: data.landscape.population_scope ?? [],
                    filterField: "population_scope",
                  },
                ]}
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
                ariaLabel="流行病学结果"
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
              <EmptyState title="未观察到匹配的流行病学数据" detail="可调整疾病、地区、指标、年份或来源条件后重试。" />
            )}
            <ResultPagination
              totalRows={data.total}
              offset={data.offset}
              pageSize={PAGE_SIZE}
              notice={publicCoverageNotice(data.warnings)}
              onPageChange={(offset) => onSearchChange(initialFilters, offset)}
              ariaLabel="流行病学结果分页"
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
        domainLabel="流行病学"
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

      {trendSelection ? (
        <section className="epidemiology-trend-panel" aria-label={`${trendSelection.diseaseName} 同口径趋势`}>
          <header>
            <div>
              <span>TREND BY COMPARABLE COHORT</span>
              <h3>
                {trendSelection.diseaseName} ·{" "}
                {epidemiologyMeasureLabels[trendSelection.filters.measure] ?? trendSelection.filters.measure}
              </h3>
              <p>
                {trendSelection.filters.geography} · {trendSelection.filters.populationScope} ·{" "}
                {trendSelection.filters.unit}
              </p>
            </div>
            <button
              className="icon-button"
              type="button"
              aria-label="关闭趋势"
              title="关闭趋势"
              onClick={() => setTrendSelection(null)}
            >
              <X size={17} />
            </button>
          </header>
          {trend.isFetching ? <Spinner label="正在读取同口径趋势" /> : null}
          {trend.error ? (
            <ErrorState
              message={trend.error instanceof Error ? trend.error.message : "趋势加载失败"}
              retry={() => void trend.refetch()}
            />
          ) : null}
          {trend.data?.items.length ? (
            <div className="trend-table-wrap">
              <Suspense fallback={<Spinner label="正在加载趋势图" />}>
                <TrendLineChart
                  ariaLabel={`${trendSelection.diseaseName} ${epidemiologyMeasureLabels[trendSelection.filters.measure] ?? trendSelection.filters.measure} 趋势图`}
                  valueLabel={trendSelection.filters.unit}
                  points={trend.data.items.map((item) => ({
                    label: periodLabel(item),
                    value: item.value,
                    lowerBound: item.lower_bound,
                    upperBound: item.upper_bound,
                  }))}
                />
              </Suspense>
              <table aria-label="同口径趋势数据">
                <thead>
                  <tr>
                    <th>观察期</th>
                    <th>估计值</th>
                    <th>区间</th>
                    <th>样本量</th>
                    <th>发布机构</th>
                    <th>方法学</th>
                  </tr>
                </thead>
                <tbody>
                  {trend.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>{periodLabel(item)}</td>
                      <td>
                        <strong>{formatNumber(item.value)}</strong> {item.unit}
                      </td>
                      <td>
                        {formatNumber(item.lower_bound)} - {formatNumber(item.upper_bound)}
                      </td>
                      <td>{formatNumber(item.sample_size)}</td>
                      <td>{item.publisher_entity?.name ?? "--"}</td>
                      <td>{item.methodology ?? "未标注"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <footer>{publicCoverageNotice(trend.data.warnings)}</footer>
            </div>
          ) : trend.data ? (
            <EmptyState title="暂无可比较趋势" detail="需要相同指标、单位、地区和人群口径的多期观测。" />
          ) : null}
        </section>
      ) : null}

      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </section>
  );
}
