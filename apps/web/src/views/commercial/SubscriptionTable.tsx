import { EmptyState, StatusBadge } from "../../components/common";
import type { CommercialOverview } from "../../lib/contracts/commercial";

export function SubscriptionTable({ items }: { items: CommercialOverview["subscriptions"] }) {
  if (!items.length) return <EmptyState title="暂无商业订阅" />;
  return (
    <div className="table-frame commercial-table">
      <table>
        <thead>
          <tr>
            <th>客户 / 订阅</th>
            <th>计费账户</th>
            <th>状态</th>
            <th>授予额度</th>
            <th>已消耗</th>
            <th>已预留</th>
            <th>可用额度</th>
            <th>今日记录</th>
            <th>权益</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.subscription_id}>
              <td>
                <strong>{item.client_name}</strong>
                <span className="cell-subtitle mono-cell">{item.subscription_key}</span>
              </td>
              <td>
                {item.billing_account_name}
                <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
              </td>
              <td>
                <StatusBadge value={item.status} />
              </td>
              <td>{item.granted_units}</td>
              <td>{item.consumed_units}</td>
              <td>{item.reserved_units}</td>
              <td>
                <strong>{item.available_units}</strong>
              </td>
              <td>{item.daily_unique_records}</td>
              <td>{item.entitlements.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
