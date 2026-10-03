import { Scale } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import type { BillingDispute, BillingDisputeFilter } from "../../lib/contracts/commercial";

export function BillingDisputeTable({
  items,
  filter,
  busy,
  onFilter,
  onAction,
}: {
  items: BillingDispute[];
  filter: BillingDisputeFilter;
  busy: string;
  onFilter: (value: BillingDisputeFilter) => void;
  onAction: (dispute: BillingDispute) => void;
}) {
  return (
    <div className="billing-operations">
      <div className="billing-section-heading">
        <h2>计费争议案件</h2>
        <label>
          <span>案件状态</span>
          <select
            aria-label="争议状态"
            value={filter}
            onChange={(event) => onFilter(event.target.value as BillingDisputeFilter)}
          >
            <option value="all">全部</option>
            <option value="open">待受理</option>
            <option value="investigating">调查中</option>
            <option value="resolved">已解决</option>
            <option value="rejected">已驳回</option>
            <option value="cancelled">已取消</option>
          </select>
        </label>
      </div>
      <div className="table-frame commercial-table">
        <table>
          <thead>
            <tr>
              <th>案件 / 主题</th>
              <th>计费账户</th>
              <th>账期单</th>
              <th>争议额度</th>
              <th>类别</th>
              <th>状态</th>
              <th>负责人</th>
              <th>SLA</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {!items.length ? (
              <tr>
                <td colSpan={9}>
                  <EmptyState title="暂无计费争议" />
                </td>
              </tr>
            ) : null}
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.subject}</strong>
                  <span className="cell-subtitle mono-cell">{item.dispute_key}</span>
                </td>
                <td>
                  {item.billing_account_name}
                  <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
                </td>
                <td className="mono-cell">{item.statement_key}</td>
                <td>{item.disputed_units}</td>
                <td>{item.category}</td>
                <td>
                  <StatusBadge value={item.status} />
                </td>
                <td>{item.assigned_to ?? "未分配"}</td>
                <td className={item.overdue ? "danger-text" : ""}>{formatDate(item.due_at, true)}</td>
                <td>
                  {["resolved", "rejected", "cancelled"].includes(item.status) ? (
                    "--"
                  ) : (
                    <button
                      className="icon-button"
                      type="button"
                      disabled={busy === `dispute:${item.id}`}
                      title="处理计费争议"
                      aria-label={`处理计费争议 ${item.dispute_key}`}
                      onClick={() => onAction(item)}
                    >
                      <Scale size={17} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
