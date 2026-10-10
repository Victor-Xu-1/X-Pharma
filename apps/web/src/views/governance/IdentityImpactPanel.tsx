import { formatDate, StatusBadge } from "../../components/common";
import type { EntityResolutionImpact } from "../../lib/contracts/governance";

const IDENTITY_DECISION_LABELS: Record<string, string> = {
  approve: "批准合并",
  reject: "保持独立",
  revert: "拆分恢复",
};

export function IdentityImpactPanel({ impact }: { impact: EntityResolutionImpact }) {
  return (
    <section className="identity-impact" aria-labelledby="identity-impact-title">
      <header>
        <div>
          <h3 id="identity-impact-title">跨域影响分析</h3>
          <p>统计当前租户所有已声明 `entities.id` 外键，不修改任何领域记录。</p>
        </div>
        <StatusBadge value={impact.rollback_available ? "rollback ready" : impact.case.status} />
      </header>
      <dl className="identity-impact-metrics">
        <div>
          <dt>来源实体引用</dt>
          <dd>{impact.source_reference_count}</dd>
        </div>
        <div>
          <dt>候选实体引用</dt>
          <dd>{impact.candidate_reference_count}</dd>
        </div>
        <div>
          <dt>来源可信标识</dt>
          <dd>{impact.source_trusted_identifier_count}</dd>
        </div>
        <div>
          <dt>候选可信标识</dt>
          <dd>{impact.candidate_trusted_identifier_count}</dd>
        </div>
      </dl>
      {impact.references.length ? (
        <div className="table-frame identity-impact-table">
          <table>
            <thead>
              <tr>
                <th>领域</th>
                <th>引用位置</th>
                <th>来源</th>
                <th>候选</th>
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
        </div>
      ) : (
        <p className="field-help">两个实体当前都没有领域引用。</p>
      )}
      {impact.decisions.length ? (
        <div className="identity-decision-history">
          <h4>不可变决策历史</h4>
          <ol>
            {impact.decisions.map((decision) => (
              <li key={decision.id}>
                <span>
                  <strong>{IDENTITY_DECISION_LABELS[decision.action] ?? decision.action}</strong>
                  <small>{formatDate(decision.created_at, true)}</small>
                </span>
                <p>{decision.notes ?? "未填写说明"}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
