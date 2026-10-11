import { EmptyState, ErrorState, formatDate, Spinner } from "../../../components/common";
import { PipelineLandscape } from "../../../components/PipelineLandscape";
import { formattingLocale, useMessages } from "../../../lib/i18n";
import { intelligenceWarningText } from "../../../lib/i18n/intelligenceWarnings";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { DrugPipeline } from "./DrugPipelineTable";
import { Pipeline } from "./ProgramPipelineTable";
import { pipelineLoadingLabel } from "./presentation";
import type { TargetPipelineProps } from "./types";
import type { TargetPipelineState } from "./useTargetPipeline";

/** Current query output only; stable controls and their lifecycle belong to the parent. */
export function TargetPipelineResults({
  state,
  props,
  hasUserFilters,
}: {
  state: TargetPipelineState;
  props: TargetPipelineProps;
  hasUserFilters: boolean;
}) {
  const text = useMessages(targetPipelineMessages);
  const {
    result,
    filters,
    displayMode,
    analysis,
    selectedDrugIds,
    visibleDrugColumns,
    applyLandscapeFilter,
    updateAnalysis,
    toggleDrug,
    updateFilter,
  } = state;
  const { targetName, fallbackItems, onOpen, onOpenEntity } = props;
  if (result.isPending) return <Spinner label={pipelineLoadingLabel(targetName, filters)} />;
  if (result.error || !result.data)
    return (
      <div>
        <ErrorState
          message={result.error instanceof Error ? result.error.message : text("研发项目查询失败")}
          retry={() => void result.refetch()}
        />
        {fallbackItems.length ? (
          <>
            <p className="inline-alert">{text("当前仅显示档案缓存中的部分记录，完整结果暂不可用。")}</p>
            <Pipeline items={fallbackItems} onOpen={onOpen} onOpenEntity={onOpenEntity} />
          </>
        ) : null}
      </div>
    );
  const data = result.data;
  const rangeStart = data.total ? data.offset + 1 : 0;
  const rangeEnd = Math.min(data.offset + data.items.length, data.total);
  const clinicalResultCount = data.facets?.has_clinical_results?.true ?? 0;
  const dealDisclosureCount = data.facets?.has_deal?.true ?? 0;
  const hasNoRelatedCoverage =
    data.total > 0 &&
    data.landscape.distinct_diseases === 0 &&
    data.landscape.distinct_organizations === 0 &&
    clinicalResultCount === 0 &&
    dealDisclosureCount === 0;
  return (
    <div className="target-pipeline-results">
      <section className="result-summary" aria-label={text("{name} 研发药物概览", { name: targetName })}>
        <span className="target-pipeline-metric">
          <strong>{(data.project_total ?? data.landscape.total_programs).toLocaleString(formattingLocale())}</strong>{" "}
          <span>{text("个研发项目")}</span>
        </span>
        <span className="target-pipeline-metric">
          <strong>{data.landscape.distinct_drugs.toLocaleString(formattingLocale())}</strong>{" "}
          <span>{text("个药物")}</span>
        </span>
      </section>
      <p className="muted-text">
        {data.total > 0 ? text("当前显示 {from}-{to} · ", { from: rangeStart, to: rangeEnd }) : ""}
        {text("查询时间")} {formatDate(data.as_of, true)}
        {data.result_grain === "drug"
          ? text("。默认按药物汇总全部匹配适应症；可切换项目明细查看每条研发记录。")
          : text("。项目明细按药物-适应症展示，加入比较时按药物去重。")}
      </p>
      <section className="pipeline-coverage-summary" aria-label={text("结果覆盖范围")}>
        <p className="muted-text">
          {text(
            "关联适应症 {diseases} 个 · 研发机构 {organizations} 家 · 临床结果 {clinical} 条 · 交易披露 {deals} 条",
            {
              diseases: data.landscape.distinct_diseases.toLocaleString(formattingLocale()),
              organizations: data.landscape.distinct_organizations.toLocaleString(formattingLocale()),
              clinical: clinicalResultCount.toLocaleString(formattingLocale()),
              deals: dealDisclosureCount.toLocaleString(formattingLocale()),
            },
          )}
        </p>
      </section>
      {hasNoRelatedCoverage ? (
        <p className="inline-alert">
          {text(
            "当前结果暂未关联适应症、研发机构、临床结果或交易披露。结果数量反映当前可检索来源中的匹配记录，不代表相关信息不存在。",
          )}
        </p>
      ) : null}
      {(data.warnings ?? []).map((warning) => (
        <p className="inline-alert" key={warning}>
          {intelligenceWarningText(warning)}
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
          <nav className="sar-pagination" aria-label={text("研发药物分页")}>
            <button
              type="button"
              disabled={data.offset === 0}
              onClick={() => updateFilter("offset", Math.max(0, data.offset - data.limit))}
            >
              {text("上一页")}
            </button>
            <span>
              {rangeStart}-{rangeEnd} / {data.total.toLocaleString(formattingLocale())}
            </span>
            <button
              type="button"
              disabled={data.offset + data.items.length >= data.total}
              onClick={() => updateFilter("offset", data.offset + data.limit)}
            >
              {text("下一页")}
            </button>
          </nav>
        </>
      ) : (
        <EmptyState
          title={
            hasUserFilters
              ? text("当前筛选条件下暂无匹配研发项目")
              : text("暂无 {name} 研发项目记录", { name: targetName })
          }
          detail={
            hasUserFilters
              ? text("调整或重置筛选条件后重试")
              : text("当前暂无可公开展示的研发项目记录；现有来源可能尚未覆盖该靶点。")
          }
        />
      )}
    </div>
  );
}
