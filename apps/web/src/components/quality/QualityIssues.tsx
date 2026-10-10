import { RefreshCw } from "lucide-react";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { EmptyState, formatDate, StatusBadge } from "../common";
import { QualityIssueDetail } from "./QualityIssueDetail";
import { QualityQueryFeedback } from "./QualityQueryFeedback";
import { ACTIVE_QUALITY_STATUSES, type QualityOperations } from "./useQualityOperations";

const filters = {
  all: "全部",
  open: "待处置",
  acknowledged: "已确认",
  ready_to_resolve: "待关闭",
  resolved: "已解决",
  waived: "已豁免",
} as const;
export function QualityIssues({ model }: { model: QualityOperations }) {
  return (
    <section className="quality-issues" aria-labelledby="quality-issues-title">
      <header>
        <div>
          <h3 id="quality-issues-title">{t("质量事件与SLA")}</h3>
          <p>{t("恢复指标只进入待关闭状态，必须由负责人复核后结案。")}</p>
        </div>
        <label>
          <span>{t("事件状态")}</span>
          <select value={model.status} disabled={model.busy} onChange={(event) => model.filter(event.target.value)}>
            {Object.entries(filters).map(([key, label]) => (
              <option key={key} value={key}>
                {t(label)}
              </option>
            ))}
          </select>
        </label>
      </header>
      <div className="quality-issue-toolbar">
        <button
          type="button"
          className="secondary-button"
          disabled={model.busy || model.issues.isFetching}
          onClick={() => void model.refreshIssues()}
        >
          <RefreshCw size={15} />
          {t("刷新质量事件")}
        </button>
      </div>
      <QualityQueryFeedback query={model.issues} label={t("正在读取质量事件")} cached={Boolean(model.issueData)} />
      <div className="quality-issue-layout">
        <section className="quality-issue-list" aria-label={t("质量事件列表")}>
          {(model.issueData ?? []).map((issue) => {
            const overdue =
              ACTIVE_QUALITY_STATUSES.has(issue.status) && new Date(issue.sla_due_at).getTime() < Date.now();
            return (
              <button
                type="button"
                key={issue.id}
                disabled={model.busy}
                aria-pressed={model.issue?.id === issue.id}
                className={model.issue?.id === issue.id ? "active" : ""}
                onClick={() => model.select(issue.id)}
              >
                <span>
                  <StatusBadge value={issue.severity} />
                  <strong>{issue.title}</strong>
                </span>
                <small>
                  {issue.owner_display_name ?? t("未分配")} ·{" "}
                  {overdue ? t("SLA已超时") : "SLA " + formatDate(issue.sla_due_at, true)}
                </small>
              </button>
            );
          })}
          {model.issues.isSuccess && !model.issueData?.length ? (
            <EmptyState title={t("没有匹配的质量事件")} detail={t("调整状态筛选或运行新评估。")} />
          ) : null}
        </section>
        <QualityIssueDetail model={model} />
      </div>
    </section>
  );
}
