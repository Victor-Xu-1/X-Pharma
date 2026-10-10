import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { EmptyState, formatDate, StatusBadge, statusLabel } from "../common";
import { QualityQueryFeedback } from "./QualityQueryFeedback";
import { QualityRawRecord } from "./QualityRawRecord";
import { qualityReportedValue } from "./qualityMetricPresentation";
import { ACTIVE_QUALITY_STATUSES, type QualityOperations } from "./useQualityOperations";

const actorLabels = { agent: "Agent", api_key: "API客户端", system: "系统", user: "用户" } as const;
function actorLabel(key: string) {
  if (!Object.hasOwn(actorLabels, key)) return key;
  const value = actorLabels[key as keyof typeof actorLabels];
  return value === "Agent" ? value : t(value);
}
export function QualityIssueDetail({ model }: { model: QualityOperations }) {
  const issue = model.issue;
  if (!issue)
    return (
      <div className="quality-issue-detail">
        {model.issues.isSuccess ? (
          <EmptyState title={t("选择质量事件")} detail={t("查看责任人、SLA 和完整处置历史。")} />
        ) : null}
      </div>
    );
  const ownerMissing = model.ownerId && !model.ownerData?.some((owner) => owner.id === model.ownerId);
  return (
    <div className="quality-issue-detail">
      <header>
        <div>
          <span>
            <StatusBadge value={issue.status} />
            <StatusBadge value={issue.severity} />
          </span>
          <h4>{issue.title}</h4>
          <p>{issue.description}</p>
        </div>
        <small>v{issue.version}</small>
      </header>
      <dl className="quality-issue-measurements">
        <div>
          <dt>{t("观测值")}</dt>
          <dd>{qualityReportedValue(issue.actual_value)}</dd>
        </div>
        <div>
          <dt>{t("比较规则")}</dt>
          <dd>{issue.comparison}</dd>
        </div>
        <div>
          <dt>{t("阈值")}</dt>
          <dd>{qualityReportedValue(issue.threshold_value)}</dd>
        </div>
        <div>
          <dt>{t("到期时间")}</dt>
          <dd>{formatDate(issue.sla_due_at, true)}</dd>
        </div>
      </dl>
      <QualityRawRecord title={t("完整事件记录")} value={issue} />
      {ACTIVE_QUALITY_STATUSES.has(issue.status) ? (
        <>
          <QualityQueryFeedback query={model.owners} label={t("正在读取负责人")} cached={Boolean(model.ownerData)} />
          <div className="quality-issue-actions">
            <label>
              <span>{t("负责人")}</span>
              <select
                value={model.ownerId}
                disabled={model.busy || !model.canAct || !model.ownerCurrent}
                onChange={(event) => model.updateDraft({ ownerId: event.target.value })}
              >
                <option value="">{t("选择负责人")}</option>
                {ownerMissing ? (
                  <option value={model.ownerId} disabled>
                    {issue.owner_display_name ?? model.ownerId} · {t("当前负责人不在可分配名单中")}
                  </option>
                ) : null}
                {(model.ownerData ?? []).map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.display_name} · {statusLabel(owner.role)}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" disabled={model.busy || !model.canAssign} onClick={() => model.submit("assign")}>
              {t("分配")}
            </button>
            <label className="quality-action-notes">
              <span>{t("处置说明")}</span>
              <textarea
                rows={3}
                maxLength={4000}
                value={model.notes}
                disabled={model.busy || !model.canAct}
                onChange={(event) => model.updateDraft({ notes: event.target.value })}
              />
            </label>
            {issue.status === "open" ? (
              <button
                type="button"
                disabled={model.busy || !model.canAcknowledge}
                onClick={() => model.submit("acknowledge")}
              >
                {issue.owner_user_id ? t("确认接手") : t("请先分配负责人")}
              </button>
            ) : null}
            {issue.status === "ready_to_resolve" &&
            (model.actor?.role === "admin" || model.actor?.id === issue.owner_user_id) ? (
              <button
                type="button"
                className="primary-button"
                disabled={model.busy || !model.canResolve}
                onClick={() => model.submit("resolve")}
              >
                {t("复核并关闭")}
              </button>
            ) : null}
            {model.actor?.role === "admin" ? (
              <button
                type="button"
                className="danger-button"
                disabled={model.busy || !model.canWaive}
                onClick={() => model.submit("waive")}
              >
                {t("记录豁免")}
              </button>
            ) : null}
            <p className="field-help quality-action-notes">
              {model.canReview
                ? t("只有负责人或管理员可以关闭事件；只有管理员可以记录豁免。")
                : t("没有当前处置权限。")}
            </p>
          </div>
        </>
      ) : null}
      <section className="quality-event-history" aria-labelledby="quality-events-title">
        <h5 id="quality-events-title">{t("不可变处置历史")}</h5>
        <QualityQueryFeedback query={model.events} label={t("正在读取处置历史")} cached={Boolean(model.eventData)} />
        {(model.eventData ?? []).map((event) => (
          <article key={event.id}>
            <span>
              <strong>{statusLabel(event.action)}</strong>
              <small>{formatDate(event.occurred_at, true)}</small>
            </span>
            <p>
              {event.previous_status ? statusLabel(event.previous_status) : "—"} → {statusLabel(event.resulting_status)}{" "}
              · {actorLabel(event.actor_type)}
            </p>
            <QualityRawRecord title={t("完整处置记录")} value={event} />
          </article>
        ))}
        {model.events.isSuccess && !model.eventData?.length ? (
          <EmptyState title={t("尚无处置历史")} detail={t("此事件尚未返回处置记录。")} />
        ) : null}
      </section>
    </div>
  );
}
