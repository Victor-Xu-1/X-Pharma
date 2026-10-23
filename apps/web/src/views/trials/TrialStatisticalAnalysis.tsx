import type { ClinicalTrialStatisticalAnalysisRead } from "../../lib/generated";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { formatResultRange } from "./presentation";

export function TrialStatisticalAnalysis({ analysis }: { analysis: ClinicalTrialStatisticalAnalysisRead }) {
  const hasBounds = analysis.lower_limit != null || analysis.upper_limit != null;
  const hasLevel = analysis.confidence_interval_percent != null;
  return (
    <article className="trial-statistical-analysis">
      <strong>{analysis.method ?? t("统计分析")}</strong>
      {analysis.parameter_type ? <span className="trial-analysis-parameter">{analysis.parameter_type}</span> : null}
      <p className="trial-analysis-values">
        {analysis.p_value != null && analysis.p_value !== "" ? `p=${analysis.p_value}` : ""}
        {analysis.parameter_value != null ? ` ${analysis.parameter_value}` : ""}
        {hasLevel ? ` · ${analysis.confidence_interval_percent}% CI` : hasBounds ? ` · ${t("置信水平未记录")}` : ""}
        {hasBounds ? ` · ${formatResultRange(analysis.lower_limit, analysis.upper_limit)}` : ""}
      </p>
      {analysis.notes ? <p className="trial-analysis-note">{analysis.notes}</p> : null}
    </article>
  );
}
