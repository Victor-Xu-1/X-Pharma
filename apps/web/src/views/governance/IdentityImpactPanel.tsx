import { formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EntityResolutionImpact } from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import { type governanceReviewMessages, governanceReviewText as t } from "../../lib/i18n/governanceReview";

const IDENTITY_DECISION_LABELS: Record<string, keyof typeof governanceReviewMessages> = {
  approve: "批准合并",
  reject: "保持独立",
  revert: "拆分恢复",
};

export function IdentityImpactPanel({
  impact,
  onRefresh,
  refreshing,
}: {
  impact: EntityResolutionImpact;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  useLocale();
  return (
    <section className="identity-impact" aria-labelledby="identity-impact-title">
      <header>
        <div>
          <h3 id="identity-impact-title">{t("跨域影响分析")}</h3>
          <p>{t("统计当前租户所有已声明 entities.id 外键，不修改任何领域记录。")}</p>
        </div>
        <StatusBadge value={impact.rollback_available ? "rollback ready" : impact.case.status} />
        <button type="button" className="secondary-button" disabled={refreshing} onClick={onRefresh}>
          {t("刷新影响分析")}
        </button>
      </header>
      <dl className="identity-impact-metrics">
        <div>
          <dt>{t("来源实体引用")}</dt>
          <dd>{impact.source_reference_count}</dd>
        </div>
        <div>
          <dt>{t("候选实体引用")}</dt>
          <dd>{impact.candidate_reference_count}</dd>
        </div>
        <div>
          <dt>{t("来源可信标识")}</dt>
          <dd>{impact.source_trusted_identifier_count}</dd>
        </div>
        <div>
          <dt>{t("候选可信标识")}</dt>
          <dd>{impact.candidate_trusted_identifier_count}</dd>
        </div>
      </dl>
      {impact.references.length ? (
        <ScrollableTableRegion ariaLabel={t("跨域影响分析")} className="table-frame identity-impact-table">
          <table>
            <thead>
              <tr>
                <th scope="col">{t("领域")}</th>
                <th scope="col">{t("引用位置")}</th>
                <th scope="col">{t("来源")}</th>
                <th scope="col">{t("候选")}</th>
              </tr>
            </thead>
            <tbody>
              {impact.references.map((item) => (
                <tr key={`${item.table}:${item.column}`}>
                  <td>{item.domain}</td>
                  <td className="mono-cell">
                    {item.table}.{item.column}
                  </td>
                  <td>{item.source_count}</td>
                  <td>{item.candidate_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <p className="field-help">
          {t(
            impact.source_reference_count === 0 && impact.candidate_reference_count === 0
              ? "两个实体当前都没有领域引用"
              : "未提供引用明细",
          )}
        </p>
      )}
      {impact.decisions.length ? (
        <div className="identity-decision-history">
          <h4>{t("不可变决策历史")}</h4>
          <ol>
            {impact.decisions.map((decision) => (
              <li key={decision.id}>
                <span>
                  <strong>
                    {Object.hasOwn(IDENTITY_DECISION_LABELS, decision.action)
                      ? t(IDENTITY_DECISION_LABELS[decision.action])
                      : decision.action}
                  </strong>
                  <small>{formatDate(decision.created_at, true)}</small>
                </span>
                <p>{decision.notes ?? t("未填写说明")}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
