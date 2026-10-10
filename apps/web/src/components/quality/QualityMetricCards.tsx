import { useLocale } from "../../lib/i18n";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { StatusBadge } from "../common";
import { QualityRawRecord } from "./QualityRawRecord";
import {
  qualityMetricKeys,
  qualityMetricLabel,
  qualityMetricValue,
  qualityReportedValue,
} from "./qualityMetricPresentation";
export function QualityMetricCards({ metrics }: { metrics: Record<string, Record<string, unknown>> }) {
  useLocale();
  return (
    <div className="quality-metric-grid">
      {qualityMetricKeys(metrics).map((key) => {
        const metric = metrics[key];
        const value = metric.applicable === false ? t("不适用") : qualityMetricValue(key, metric.value);
        const relation =
          metric.comparison === "gte"
            ? "≥"
            : metric.comparison === "lte"
              ? "≤"
              : metric.comparison == null
                ? ""
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
              {metric.numerator == null && metric.denominator == null
                ? t("样本量未上报")
                : t("样本 {numerator}/{denominator}", {
                    numerator: qualityReportedValue(metric.numerator),
                    denominator: qualityReportedValue(metric.denominator),
                  })}
            </small>
            <small>
              {t("阈值")} {relation} {qualityMetricValue(key, metric.threshold)}
            </small>
            <QualityRawRecord title={t("原始指标记录")} value={metric} />
          </article>
        );
      })}
    </div>
  );
}
