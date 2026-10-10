import { formattingLocale } from "../../lib/i18n";
import { type governanceQualityMessages, governanceQualityText as t } from "../../lib/i18n/governanceQuality";
export const QUALITY_METRIC_ORDER = [
  "completeness",
  "duplicate_rate",
  "citation_coverage",
  "freshness_coverage",
  "ingestion_success",
  "drift",
] as const;
const labels: Record<string, keyof typeof governanceQualityMessages> = {
  completeness: "完整率",
  duplicate_rate: "重复率",
  citation_coverage: "引用覆盖率",
  freshness_coverage: "新鲜度覆盖率",
  ingestion_success: "入库成功率",
  drift: "指标漂移",
};
export function qualityMetricKeys(metrics: Record<string, Record<string, unknown>>): string[] {
  return [
    ...QUALITY_METRIC_ORDER.filter((key) => Object.hasOwn(metrics, key)),
    ...Object.keys(metrics).filter((key) => !QUALITY_METRIC_ORDER.some((known) => known === key)),
  ];
}
export function qualityMetricLabel(key: string, metric: Record<string, unknown>): string {
  return Object.hasOwn(labels, key) ? t(labels[key]) : typeof metric.label === "string" ? metric.label : key;
}
export function qualityReportedValue(value: unknown): string {
  return value === null || value === undefined
    ? t("未上报")
    : typeof value === "string"
      ? value
      : (JSON.stringify(value) ?? t("未上报"));
}
export function qualityPercent(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return qualityReportedValue(value);
  const tiny = value !== 0 && Math.abs(value * 100) < 0.05;
  return new Intl.NumberFormat(
    formattingLocale(),
    tiny
      ? { style: "percent", maximumSignificantDigits: 3 }
      : { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 },
  ).format(value);
}
