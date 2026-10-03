import { AppliedFiltersBar } from "../../../components/AppliedFiltersBar";
import { EmptyState, ErrorState, formatDate, Spinner } from "../../../components/common";
import { PipelineLandscape } from "../../../components/PipelineLandscape";
import { hasPipelineSearchFilter } from "../../../lib/contracts/pipeline";
import {
  isPublicProgramTag,
  programModalityLabel,
  programTagLabel,
  publicProgramTags,
} from "../../../lib/programDisplay";
import { DrugPipeline } from "./DrugPipelineTable";
import { PipelineAdvancedFilters } from "./PipelineAdvancedFilters";
import { PipelinePrimaryFilters } from "./PipelinePrimaryFilters";
import { Pipeline } from "./ProgramPipelineTable";
import {
  countAdvancedPipelineFilters,
  developmentPhaseLabels,
  geographyLabels,
  pipelineLoadingLabel,
  targetPipelineAppliedFilterLabels,
  targetPipelineAppliedFilters,
} from "./presentation";
import { TargetPipelineToolbar } from "./TargetPipelineToolbar";
import type { TargetPipelineProps } from "./types";
import { useTargetPipeline } from "./useTargetPipeline";

export function TargetPipeline(props: TargetPipelineProps) {
  const { targetName, fallbackItems, onOpen, onOpenEntity, onOpenComparison } = props;
  const state = useTargetPipeline(props);
  const {
    filters,
    result,
    displayMode,
    analysis,
    selectedDrugIds,
    visibleDrugColumns,
    cachedFacetOptions,
    resetFilters,
    applyLandscapeFilter,
    updateAnalysis,
    toggleDrug,
    updateFilter,
  } = state;
  if (result.isPending) {
    return <Spinner label={pipelineLoadingLabel(targetName, filters)} />;
  }
  if (result.error || !result.data) {
    return (
      <div>
        <ErrorState
          message={result.error instanceof Error ? result.error.message : "研发项目查询失败"}
          retry={() => void result.refetch()}
        />
        {fallbackItems.length ? (
          <>
            <p className="inline-alert">当前仅显示档案缓存中的部分记录，完整结果暂不可用。</p>
            <Pipeline items={fallbackItems} onOpen={onOpen} onOpenEntity={onOpenEntity} />
          </>
        ) : null}
      </div>
    );
  }

  const data = result.data;
  const hasUserFilters = hasPipelineSearchFilter({
    ...filters,
    targetEntityId: "",
    programStatus: filters.programStatus === "active" ? "" : filters.programStatus,
  });
  const rangeStart = data.total ? data.offset + 1 : 0;
  const rangeEnd = Math.min(data.offset + data.items.length, data.total);
  const pageDrugIds =
    displayMode === "drug"
      ? [...new Set(data.items.map((item) => item.drug_entity_id).filter((value): value is string => Boolean(value)))]
      : [];
  const selectedPageDrugCount = pageDrugIds.filter((drugId) => selectedDrugIds.has(drugId)).length;
  const allPageDrugsSelected = pageDrugIds.length > 0 && selectedPageDrugCount === pageDrugIds.length;
  const advancedFilterCount = countAdvancedPipelineFilters(filters);
  const clinicalResultCount = data.facets?.has_clinical_results?.true ?? 0;
  const dealDisclosureCount = data.facets?.has_deal?.true ?? 0;
  const hasNoRelatedCoverage =
    data.total > 0 &&
    data.landscape.distinct_diseases === 0 &&
    data.landscape.distinct_organizations === 0 &&
    clinicalResultCount === 0 &&
    dealDisclosureCount === 0;
  const programTagOptions = cachedFacetOptions("program_tag", data.facets?.program_tag, filters.programTags)
    .filter((option) => isPublicProgramTag(option.value))
    .map((option) => ({ ...option, label: programTagLabel(option.value) }));

  return (
    <div className="target-pipeline-panel">
      <section className="result-summary" aria-label={`${targetName} 研发药物概览`}>
        <span>
          <strong>{(data.project_total ?? data.landscape.total_programs).toLocaleString("zh-CN")}</strong> 个研发项目
        </span>
        <span>
          <strong>{data.landscape.distinct_drugs.toLocaleString("zh-CN")}</strong> 个药物
        </span>
      </section>
      <p className="muted-text">
        {data.total > 0 ? `当前显示 ${rangeStart}-${rangeEnd} · ` : ""}查询时间 {formatDate(data.as_of, true)}
        {data.result_grain === "drug"
          ? "。默认按药物汇总全部匹配适应症；可切换项目明细查看每条研发记录。"
          : "。项目明细按药物-适应症展示，加入比较时按药物去重。"}
      </p>
      <section className="pipeline-coverage-summary" aria-label="结果覆盖范围">
        <p className="muted-text">
          {`关联适应症 ${data.landscape.distinct_diseases.toLocaleString("zh-CN")} 个 · 研发机构 ${data.landscape.distinct_organizations.toLocaleString("zh-CN")} 家 · 临床结果 ${clinicalResultCount.toLocaleString("zh-CN")} 条 · 交易披露 ${dealDisclosureCount.toLocaleString("zh-CN")} 条`}
        </p>
      </section>
      {hasNoRelatedCoverage ? (
        <p className="inline-alert">
          当前结果暂未关联适应症、研发机构、临床结果或交易披露。结果数量反映当前可检索来源中的匹配记录，不代表相关信息不存在。
        </p>
      ) : null}
      <TargetPipelineToolbar
        state={state}
        pageDrugIds={pageDrugIds}
        allPageDrugsSelected={allPageDrugsSelected}
        onOpenComparison={onOpenComparison}
      />
      <PipelinePrimaryFilters
        state={state}
        data={data}
        hasUserFilters={hasUserFilters}
        onFiltersChange={props.onFiltersChange}
      />
      <AppliedFiltersBar
        filters={targetPipelineAppliedFilters(filters, data.landscape)}
        labels={targetPipelineAppliedFilterLabels}
        valueLabels={{
          modality: Object.fromEntries(filters.modalities.map((value) => [value, programModalityLabel(value)])),
          program_tag: Object.fromEntries(
            publicProgramTags(filters.programTags).map((value) => [value, programTagLabel(value)]),
          ),
          program_status: { inactive: "已停止", unknown: "状态未披露" },
          phase: developmentPhaseLabels,
          global_phase: developmentPhaseLabels,
          china_phase: developmentPhaseLabels,
          geography: geographyLabels,
          clinical_result: { true: "已有结果", false: "暂无结果" },
          deal: { true: "已有交易", false: "暂无交易" },
        }}
        onClear={hasUserFilters ? resetFilters : undefined}
      />
      <PipelineAdvancedFilters
        state={state}
        data={data}
        advancedFilterCount={advancedFilterCount}
        programTagOptions={programTagOptions}
      />
      {(data.warnings ?? []).map((warning) => (
        <p className="inline-alert" key={warning}>
          {warning}
        </p>
      ))}
      {displayMode === "landscape" ? (
        <PipelineLandscape
          landscape={data.landscape}
          dimension={analysis.dimension}
          view={analysis.view}
          limit={analysis.limit}
          stageScope={analysis.stageScope}
          targetAggregation={analysis.targetAggregation}
          onFilter={applyLandscapeFilter}
          onOpenEntity={(entityId) => onOpenEntity("drug", entityId)}
          onOpenTarget={(entityId) => onOpenEntity("target", entityId)}
          onOpenDisease={(entityId) => onOpenEntity("disease", entityId)}
          onOpenOrganization={(entityId) => onOpenEntity("organization", entityId)}
          onAnalysisChange={updateAnalysis}
        />
      ) : data.items.length ? (
        <>
          {data.result_grain === "drug" ? (
            <DrugPipeline
              items={data.items}
              onOpenEntity={onOpenEntity}
              selectedDrugIds={selectedDrugIds}
              onToggleDrug={toggleDrug}
              visibleColumns={visibleDrugColumns}
            />
          ) : (
            <Pipeline
              items={data.items}
              onOpen={onOpen}
              onOpenEntity={onOpenEntity}
              selectedDrugIds={selectedDrugIds}
              onToggleDrug={toggleDrug}
            />
          )}
          <nav className="sar-pagination" aria-label="研发药物分页">
            <button
              type="button"
              disabled={data.offset === 0}
              onClick={() => updateFilter("offset", Math.max(0, data.offset - data.limit))}
            >
              上一页
            </button>
            <span>
              {rangeStart}-{rangeEnd} / {data.total.toLocaleString("zh-CN")}
            </span>
            <button
              type="button"
              disabled={data.offset + data.items.length >= data.total}
              onClick={() => updateFilter("offset", data.offset + data.limit)}
            >
              下一页
            </button>
          </nav>
        </>
      ) : (
        <EmptyState
          title={hasUserFilters ? "当前筛选条件下暂无匹配研发项目" : `暂无 ${targetName} 研发项目记录`}
          detail={
            hasUserFilters
              ? "调整或重置筛选条件后重试"
              : "当前暂无可公开展示的研发项目记录；来源资料正在完成质量核查或尚未覆盖该靶点。"
          }
        />
      )}
    </div>
  );
}
