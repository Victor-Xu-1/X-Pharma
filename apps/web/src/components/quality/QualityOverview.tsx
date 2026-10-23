import { AlertTriangle, RotateCcw } from "lucide-react";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { EmptyState } from "../common";
import { QualityMetricCards } from "./QualityMetricCards";
import { QualityQueryFeedback } from "./QualityQueryFeedback";
import { ACTIVE_QUALITY_STATUSES, type QualityOperations } from "./useQualityOperations";
export function QualityOverview({ model }: { model: QualityOperations }) {
  const latest = model.snapshotData?.[0];
  const active = (model.issueData ?? []).filter((issue) => ACTIVE_QUALITY_STATUSES.has(issue.status));
  const overdue = active.filter((issue) => new Date(issue.sla_due_at).getTime() < Date.now());
  return (
    <section className="quality-overview" aria-labelledby="quality-overview-title">
      <header>
        <div>
          <h2 id="quality-overview-title">{t("数据质量运营")}</h2>
          <p>
            {t("指标定义 {version}", { version: latest?.definitions_version ?? t("未上报") })} ·{" "}
            {t("所有处置写入不可变事件历史。")}
          </p>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={model.busy || !model.canEvaluate}
          onClick={model.evaluate}
        >
          <RotateCcw size={16} />
          {model.intent === "quality-evaluation" ? t("正在评估") : t("立即评估")}
        </button>
      </header>
      <QualityQueryFeedback query={model.snapshots} label={t("正在读取质量快照")} cached={Boolean(latest)} />
      {latest ? (
        <QualityMetricCards metrics={latest.metrics} />
      ) : model.snapshots.isSuccess ? (
        <EmptyState title={t("尚无质量快照")} detail={t("运行一次评估以建立首个质量基线")} />
      ) : null}
      {active.length ? (
        <div className="factory-warning" role="status">
          <AlertTriangle size={17} />
          <span>
            <strong>{t("仍有待处置质量事件")}</strong>
            {t("当前快照之外仍有 {count} 个事件尚未结案", { count: active.length })}
            {overdue.length ? t("，其中 {count} 个已超过 SLA", { count: overdue.length }) : ""}
            {t("；请在下方复核并关闭或记录豁免。")}
          </span>
        </div>
      ) : null}
    </section>
  );
}
