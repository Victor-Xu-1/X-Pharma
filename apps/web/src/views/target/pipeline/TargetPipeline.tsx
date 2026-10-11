import { AppliedFiltersBar } from "../../../components/AppliedFiltersBar";
import { hasPipelineSearchFilter } from "../../../lib/contracts/pipeline";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import {
  isPublicProgramTag,
  programModalityLabel,
  programTagLabel,
  publicProgramTags,
} from "../../../lib/programDisplay";
import { PipelineAdvancedFilters } from "./PipelineAdvancedFilters";
import { PipelinePrimaryFilters } from "./PipelinePrimaryFilters";
import {
  countAdvancedPipelineFilters,
  developmentPhaseLabel,
  developmentPhaseLabels,
  geographyLabel,
  geographyLabels,
  targetPipelineAppliedFilterLabels,
  targetPipelineAppliedFilters,
} from "./presentation";
import { TargetPipelineResults } from "./TargetPipelineResults";
import { TargetPipelineToolbar } from "./TargetPipelineToolbar";
import type { TargetPipelineProps } from "./types";
import { useTargetPipeline } from "./useTargetPipeline";

export function TargetPipeline(props: TargetPipelineProps) {
  const text = useMessages(targetPipelineMessages);
  const state = useTargetPipeline(props);
  const { filters, result, displayMode, selectedDrugIds, cachedFacetOptions, resetFilters, filterFacets } = state;
  const hasUserFilters = hasPipelineSearchFilter({
    ...filters,
    targetEntityId: "",
    programStatus: filters.programStatus === "active" ? "" : filters.programStatus,
  });
  const hasCurrentResult = !result.isPending && !result.error && Boolean(result.data);
  const pageDrugIds =
    hasCurrentResult && displayMode === "drug"
      ? [
          ...new Set(
            result.data?.items.map((item) => item.drug_entity_id).filter((value): value is string => Boolean(value)),
          ),
        ]
      : [];
  const allPageDrugsSelected = pageDrugIds.length > 0 && pageDrugIds.every((drugId) => selectedDrugIds.has(drugId));
  const optionData = { facets: filterFacets };
  const programTagOptions = cachedFacetOptions("program_tag", filterFacets?.program_tag, filters.programTags)
    .filter((option) => isPublicProgramTag(option.value))
    .map((option) => ({ ...option, label: programTagLabel(option.value) }));
  const phaseLabels = Object.fromEntries(
    Object.keys(developmentPhaseLabels).map((key) => [key, developmentPhaseLabel(key)]),
  );
  const regionLabels = Object.fromEntries(Object.keys(geographyLabels).map((key) => [key, geographyLabel(key)]));

  return (
    <div className="target-pipeline-panel">
      <TargetPipelineToolbar
        state={state}
        pageDrugIds={pageDrugIds}
        allPageDrugsSelected={allPageDrugsSelected}
        onOpenComparison={props.onOpenComparison}
      />
      <PipelinePrimaryFilters
        state={state}
        data={optionData}
        hasUserFilters={hasUserFilters}
        onFiltersChange={props.onFiltersChange}
      />
      <AppliedFiltersBar
        filters={targetPipelineAppliedFilters(filters, hasCurrentResult ? result.data?.landscape : undefined)}
        labels={Object.fromEntries(
          Object.entries(targetPipelineAppliedFilterLabels).map(([key, caption]) => [key, text(caption)]),
        )}
        valueLabels={{
          modality: Object.fromEntries(filters.modalities.map((value) => [value, programModalityLabel(value)])),
          program_tag: Object.fromEntries(
            publicProgramTags(filters.programTags).map((value) => [value, programTagLabel(value)]),
          ),
          program_status: { inactive: text("已停止"), unknown: text("状态未披露") },
          phase: phaseLabels,
          global_phase: phaseLabels,
          china_phase: phaseLabels,
          geography: regionLabels,
          clinical_result: { true: text("已有结果"), false: text("暂无结果") },
          deal: { true: text("已有交易"), false: text("暂无交易") },
        }}
        onClear={hasUserFilters ? resetFilters : undefined}
      />
      <PipelineAdvancedFilters
        state={state}
        data={optionData}
        advancedFilterCount={countAdvancedPipelineFilters(filters)}
        programTagOptions={programTagOptions}
      />
      {!hasCurrentResult && filterFacets ? (
        <p className="muted-text">
          {result.error
            ? text("筛选选项来自上一次完成的查询；当前查询失败，请调整筛选或重试。")
            : text("筛选选项来自上一次完成的查询；当前结果仍在更新。")}
        </p>
      ) : null}
      <TargetPipelineResults state={state} props={props} hasUserFilters={hasUserFilters} />
    </div>
  );
}
