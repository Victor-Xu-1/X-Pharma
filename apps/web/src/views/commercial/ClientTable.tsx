import { Ban, Power } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialClient } from "../../lib/contracts/commercial";
import type { ClientAction } from "./types";

export function ClientTable({
  items,
  busy,
  onAction,
}: {
  items: CommercialClient[];
  busy: string;
  onAction: (action: ClientAction) => void;
}) {
  if (!items.length) return <EmptyState title="暂无 Agent 客户端" />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel="Agent 客户端滚动区域">
      <table aria-label="Agent 客户端">
        <thead>
          <tr>
            <th>客户端</th>
            <th>订阅</th>
            <th>计费账户</th>
            <th>状态</th>
            <th>主体</th>
            <th>可用额度</th>
            <th>活跃预留</th>
            <th>24h 拒绝</th>
            <th>最近策略事件</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.display_name}</strong>
                <span className="cell-subtitle mono-cell">{item.client_key}</span>
              </td>
              <td className="mono-cell">{item.subscription_key ?? "--"}</td>
              <td className="mono-cell">{item.billing_account_key ?? "--"}</td>
              <td>
                <StatusBadge value={item.active ? "active" : "revoked"} />
              </td>
              <td>{item.subjects.filter((subject) => subject.active).length}</td>
              <td>{item.available_units ?? "--"}</td>
              <td>{item.active_reservations}</td>
              <td className={item.denial_count_24h ? "danger-text" : ""}>{item.denial_count_24h}</td>
              <td>{formatDate(item.last_policy_event_at, true)}</td>
              <td>
                <button
                  className={item.active ? "icon-button danger-text" : "icon-button"}
                  type="button"
                  disabled={busy === `client:${item.id}`}
                  title={item.active ? "停用客户端" : "重新启用"}
                  aria-label={`${item.active ? "停用" : "启用"} ${item.display_name}`}
                  onClick={() => onAction({ client: item, active: !item.active })}
                >
                  {item.active ? <Ban size={17} /> : <Power size={17} />}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
