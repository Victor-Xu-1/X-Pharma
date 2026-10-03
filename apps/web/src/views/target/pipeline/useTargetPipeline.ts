import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { PipelineLandscapeFilterField } from "../../../components/PipelineLandscape";
import {
  emptyPipelineSearchFilters,
  type PipelineAnalysisDimension,
  type PipelineAnalysisLimit,
  type PipelineAnalysisStageScope,
  type PipelineResultGrain,
  type PipelineSearchFilters,
  type PipelineSortField,
  type PipelineTargetAggregation,
  pipelineKeys,
  type SortDirection,
  searchPipelines,
} from "../../../lib/contracts/pipeline";
import {
  countAdvancedPipelineFilters,
  defaultTargetDrugColumns,
  type TargetDrugColumnKey,
  type TargetFacetKey,
  targetFacetOptions,
} from "./presentation";
import type { TargetPipelineOptions } from "./types";

export function useTargetPipeline({
  targetId,
  initialFilters,
  onFiltersChange,
  onLandscapeFilterApply,
  initialDisplayMode,
  onDisplayModeChange,
  initialAnalysis,
  onAnalysisChange,
}: TargetPipelineOptions) {
  const fallbackFilters: PipelineSearchFilters = {
    ...emptyPipelineSearchFilters(),
    targetEntityId: targetId,
  };
  const effectiveInitialFilters = initialFilters ?? fallbackFilters;
  const initialFiltersKey = JSON.stringify(effectiveInitialFilters);
  const [filters, setFilters] = useState<PipelineSearchFilters>(effectiveInitialFilters);
  const lastInitialFiltersKey = useRef(initialFiltersKey);
  useEffect(() => {
    if (lastInitialFiltersKey.current === initialFiltersKey) return;
    lastInitialFiltersKey.current = initialFiltersKey;
    setFilters(effectiveInitialFilters);
  }, [effectiveInitialFilters, initialFiltersKey]);
  const effectiveInitialDisplayMode = initialDisplayMode ?? "drug";
  const initialDisplayModeKey = effectiveInitialDisplayMode;
  const [displayMode, setDisplayMode] = useState<"drug" | "program" | "landscape">(effectiveInitialDisplayMode);
  const lastInitialDisplayModeKey = useRef(initialDisplayModeKey);
  useEffect(() => {
    if (lastInitialDisplayModeKey.current === initialDisplayModeKey) return;
    lastInitialDisplayModeKey.current = initialDisplayModeKey;
    setDisplayMode(effectiveInitialDisplayMode);
  }, [effectiveInitialDisplayMode, initialDisplayModeKey]);
  const effectiveInitialAnalysis = initialAnalysis ?? {
    dimension: "all" as PipelineAnalysisDimension,
    view: "chart" as const,
    limit: 20 as PipelineAnalysisLimit,
    stageScope: "overall" as PipelineAnalysisStageScope,
    targetAggregation: "all" as PipelineTargetAggregation,
  };
  const initialAnalysisKey = JSON.stringify(effectiveInitialAnalysis);
  const [analysis, setAnalysis] = useState(effectiveInitialAnalysis);
  const lastInitialAnalysisKey = useRef(initialAnalysisKey);
  useEffect(() => {
    if (lastInitialAnalysisKey.current === initialAnalysisKey) return;
    lastInitialAnalysisKey.current = initialAnalysisKey;
    setAnalysis(effectiveInitialAnalysis);
  }, [effectiveInitialAnalysis, initialAnalysisKey]);
  const [selectedDrugIds, setSelectedDrugIds] = useState<Set<string>>(() => new Set());
  const [visibleDrugColumns, setVisibleDrugColumns] = useState<Set<TargetDrugColumnKey>>(defaultTargetDrugColumns);
  const [comparisonMessage, setComparisonMessage] = useState("");
  const [comparisonTarget, setComparisonTarget] = useState<{
    comparisonSetId: string;
    entityIds: string[];
  } | null>(null);
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);
  const targetFacetCache = useRef<{
    targetId: string;
    values: Partial<Record<TargetFacetKey, Record<string, number>>>;
  }>({ targetId, values: {} });
  if (targetFacetCache.current.targetId !== targetId) {
    targetFacetCache.current = { targetId, values: {} };
  }

  function cachedFacetOptions(
    key: TargetFacetKey,
    values: Record<string, number> | undefined,
    selected: readonly string[],
  ) {
    const cachedValues = targetFacetCache.current.values[key] ?? {};
    Object.assign(cachedValues, values ?? {});
    for (const value of selected) {
      if (!(value in cachedValues)) cachedValues[value] = values?.[value] ?? 0;
    }
    targetFacetCache.current.values[key] = cachedValues;
    return targetFacetOptions(cachedValues);
  }

  const advancedFilterCountForState = countAdvancedPipelineFilters(filters);
  useEffect(() => {
    setAdvancedFiltersOpen(advancedFilterCountForState > 0);
  }, [advancedFilterCountForState]);
  const [debouncedPipelineQuery, setDebouncedPipelineQuery] = useState(effectiveInitialFilters.query);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedPipelineQuery(filters.query), 250);
    return () => window.clearTimeout(timeout);
  }, [filters.query]);
  const queryAnalysis = {
    limit: analysis.limit,
    stageScope: analysis.stageScope,
    targetAggregation: analysis.targetAggregation,
  };
  const resultGrain: PipelineResultGrain = displayMode === "program" ? "program" : "drug";
  const queryFilters =
    debouncedPipelineQuery === filters.query ? filters : { ...filters, query: debouncedPipelineQuery };
  const result = useQuery({
    queryKey: pipelineKeys.search(queryFilters, queryAnalysis, resultGrain),
    queryFn: ({ signal }) => searchPipelines(queryFilters, queryAnalysis, signal, resultGrain),
  });

  function updateFilter<Key extends keyof PipelineSearchFilters>(key: Key, value: PipelineSearchFilters[Key]) {
    setComparisonMessage("");
    const nextFilters = { ...filters, [key]: value, offset: key === "offset" ? Number(value) : 0 };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
  }

  function updateSorting(value: string) {
    const [field, direction] = value.split(":") as [PipelineSortField, SortDirection];
    setComparisonMessage("");
    const nextFilters = {
      ...filters,
      sortBy: field,
      sortDirection: direction,
      sort: [{ field, direction }],
      offset: 0,
    };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
  }

  function resetFilters() {
    const nextFilters = { ...emptyPipelineSearchFilters(), targetEntityId: targetId };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
    setComparisonMessage("");
  }

  function updateDisplayMode(nextDisplayMode: "drug" | "program" | "landscape") {
    setDisplayMode(nextDisplayMode);
    onDisplayModeChange?.(nextDisplayMode);
  }

  function updateAnalysis(nextAnalysis: typeof analysis) {
    setAnalysis(nextAnalysis);
    onAnalysisChange?.(nextAnalysis);
  }

  function applyLandscapeFilter(field: PipelineLandscapeFilterField, value: string) {
    if (field === "targetEntityId") return;
    const nextFilters = {
      ...filters,
      ...(field === "modality" ? { modalities: value ? [value] : [] } : { [field]: value }),
      offset: 0,
    };
    setComparisonMessage("");
    setFilters(nextFilters);
    setDisplayMode("drug");
    if (onLandscapeFilterApply) {
      onLandscapeFilterApply(nextFilters, "drug");
      return;
    }
    onFiltersChange?.(nextFilters);
    onDisplayModeChange?.("drug");
  }

  function toggleDrug(drugId: string, selected: boolean) {
    setSelectedDrugIds((current) => {
      const next = new Set(current);
      if (selected) next.add(drugId);
      else next.delete(drugId);
      return next;
    });
    setComparisonMessage("");
  }

  function toggleDrugColumn(column: TargetDrugColumnKey, visible: boolean) {
    setVisibleDrugColumns((current) => {
      const next = new Set(current);
      if (visible) next.add(column);
      else next.delete(column);
      return next;
    });
  }

  function togglePageDrugSelection(pageDrugIds: string[], allPageDrugsSelected: boolean) {
    setSelectedDrugIds((current) => {
      const next = new Set(current);
      if (allPageDrugsSelected) {
        pageDrugIds.forEach((drugId) => {
          next.delete(drugId);
        });
      } else {
        pageDrugIds.forEach((drugId) => {
          next.add(drugId);
        });
      }
      return next;
    });
    setComparisonMessage("");
  }

  function clearDrugSelection() {
    setSelectedDrugIds(new Set());
    setComparisonMessage("");
  }

  return {
    filters,
    setFilters,
    displayMode,
    analysis,
    selectedDrugIds,
    setSelectedDrugIds,
    visibleDrugColumns,
    setVisibleDrugColumns,
    comparisonMessage,
    setComparisonMessage,
    comparisonTarget,
    setComparisonTarget,
    advancedFiltersOpen,
    setAdvancedFiltersOpen,
    cachedFacetOptions,
    result,
    updateFilter,
    updateSorting,
    resetFilters,
    updateDisplayMode,
    updateAnalysis,
    applyLandscapeFilter,
    toggleDrug,
    toggleDrugColumn,
    togglePageDrugSelection,
    clearDrugSelection,
  };
}

export type TargetPipelineState = ReturnType<typeof useTargetPipeline>;
