import { BarChart3, List } from "lucide-react";
import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineTargetAggregation,
} from "../../lib/contracts/pipeline";
import { type pipelineLandscapeMessages, pipelineLandscapeText as t } from "../../lib/i18n/pipelineLandscape";
import type { PipelineLandscapeProps } from "./types";

const dimensionOptions: Array<{ value: PipelineAnalysisDimension; label: keyof typeof pipelineLandscapeMessages }> = [
  { value: "all", label: "全部维度" },
  { value: "global_phase", label: "全球研发阶段" },
  { value: "china_phase", label: "中国研发阶段" },
  { value: "targets", label: "靶点" },
  { value: "target_combinations", label: "靶点组合" },
  { value: "diseases", label: "适应症" },
  { value: "organizations", label: "研发机构" },
  { value: "modality", label: "药物类型" },
  { value: "geography", label: "地区分布" },
];

export function AnalysisControls({
  dimension,
  view,
  limit,
  stageScope,
  targetAggregation,
  onAnalysisChange,
}: Pick<
  PipelineLandscapeProps,
  "dimension" | "view" | "limit" | "stageScope" | "targetAggregation" | "onAnalysisChange"
>) {
  const dimensionCaption = dimensionOptions.find((option) => option.value === dimension)?.label;
  return (
    <fieldset className="pipeline-analysis-toolbar">
      <legend className="sr-only">{t("竞争格局分析控制")}</legend>
      <label>
        <span>{t("分析维度")}</span>
        <select
          aria-label={t("分析维度")}
          value={dimension}
          onChange={(event) =>
            onAnalysisChange({
              dimension: event.target.value as PipelineAnalysisDimension,
              view,
              limit,
              stageScope,
              targetAggregation,
            })
          }
        >
          {dimensionOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {t(option.label)}
            </option>
          ))}
        </select>
      </label>
      <fieldset className="segmented-control">
        <legend className="sr-only">{t("分析展示方式")}</legend>
        <button
          type="button"
          aria-pressed={view === "chart"}
          onClick={() => onAnalysisChange({ dimension, view: "chart", limit, stageScope, targetAggregation })}
        >
          <BarChart3 size={14} />
          {t("图表")}
        </button>
        <button
          type="button"
          aria-pressed={view === "table"}
          onClick={() => onAnalysisChange({ dimension, view: "table", limit, stageScope, targetAggregation })}
        >
          <List size={14} />
          {t("表格")}
        </button>
      </fieldset>
      <label>
        <span>{t("显示范围")}</span>
        <select
          aria-label={t("分析显示范围")}
          value={limit}
          onChange={(event) =>
            onAnalysisChange({
              dimension,
              view,
              limit: Number(event.target.value) as PipelineAnalysisLimit,
              stageScope,
              targetAggregation,
            })
          }
        >
          <option value={5}>Top 5</option>
          <option value={8}>Top 8</option>
          <option value={20}>Top 20</option>
          <option value={50}>Top 50</option>
          <option value={100}>Top 100</option>
          <option value={200}>Top 200</option>
        </select>
      </label>
      <label>
        <span>{t("阶段口径")}</span>
        <select
          aria-label={t("阶段分析口径")}
          value={stageScope}
          onChange={(event) =>
            onAnalysisChange({
              dimension,
              view,
              limit,
              stageScope: event.target.value as PipelineAnalysisStageScope,
              targetAggregation,
            })
          }
        >
          <option value="overall">{t("总体最高阶段")}</option>
          <option value="global">{t("全球最高阶段")}</option>
          <option value="china">{t("中国最高阶段")}</option>
        </select>
      </label>
      <label>
        <span>{t("靶点聚合")}</span>
        <select
          aria-label={t("靶点聚合口径")}
          value={targetAggregation}
          onChange={(event) =>
            onAnalysisChange({
              dimension,
              view,
              limit,
              stageScope,
              targetAggregation: event.target.value as PipelineTargetAggregation,
            })
          }
        >
          <option value="all">{t("全部靶点")}</option>
          <option value="primary">{t("主靶点")}</option>
        </select>
      </label>
      <output aria-live="polite">
        {dimensionCaption ? t(dimensionCaption) : ""} · {view === "chart" ? t("图表") : t("表格")} · Top {limit} ·{" "}
        {t(stageScope === "overall" ? "总体阶段" : stageScope === "global" ? "全球阶段" : "中国阶段")}
        {targetAggregation === "primary" ? ` · ${t("主靶点")}` : ""}
      </output>
    </fieldset>
  );
}
