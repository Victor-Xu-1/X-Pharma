import { useLocale } from "../../lib/i18n";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { StatusBadge } from "../common";
import {
  qualityMetricKeys,
  qualityMetricLabel,
  qualityPercent,
  qualityReportedValue,
} from "./qualityMetricPresentation";
export function QualityMetricCards({ metrics }: { metrics: Record<string, Record<string, unknown>> }) {
  useLocale();
  return (
    <div className="quality-metric-grid">
      {qualityMetricKeys(metrics).map((key) => {
        const metric = metrics[key];
        const value = metric.applicable === false ? t("不适用") : qualityPercent(metric.value);
        const relation =
          metric.comparison === "gte"
            ? "≥"
            : metric.comparison === "lte"
              ? "≤"
              : qualityReportedValue(metric.comparison);
        return (
          <article key={key}>
            <span>
              <strong>{qualityMetricLabel(key, metric)}</strong>
              {typeof metric.status === "string" ? <StatusBadge value={metric.status} /> : null}
            </span>
            <b>{value}</b>
            {typeof metric.applicable !== "boolean" ? <p className="field-help">{t("适用性未上报")}</p> : null}
            <small>
              {t("样本 {numerator}/{denominator}", {
                numerator: qualityReportedValue(metric.numerator),
                denominator: qualityReportedValue(metric.denominator),
              })}
            </small>
            <small>
              {t("阈值")} {relation} {qualityPercent(metric.threshold)}
            </small>
            <details>
              <summary>{t("原始指标记录")}</summary>
              <pre className="json-preview compact">{JSON.stringify(metric, null, 2)}</pre>
            </details>
          </article>
        );
      })}
    </div>
  );
}
