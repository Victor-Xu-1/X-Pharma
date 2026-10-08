import { Check, ExternalLink, Search } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { MonitoringAlert } from "../../lib/contracts/monitoring";

export function MonitoringAlerts({
  alerts,
  unreadOnly,
  pending,
  onUnreadOnlyChange,
  onOpenEntity,
  onReplay,
  onMarkRead,
}: {
  alerts: MonitoringAlert[];
  unreadOnly: boolean;
  pending: ReadonlySet<string>;
  onUnreadOnlyChange: (value: boolean) => void;
  onOpenEntity: (id: string) => void;
  onReplay: (id: string) => void;
  onMarkRead: (alert: MonitoringAlert) => void;
}) {
  return (
    <>
      <div className="section-toolbar">
        <label className="check-control">
          <input type="checkbox" checked={unreadOnly} onChange={(event) => onUnreadOnlyChange(event.target.checked)} />
          仅看未读
        </label>
        <span>{alerts.filter((item) => !item.read_at).length} 条未读</span>
      </div>
      {alerts.length ? (
        <ScrollableTableRegion ariaLabel="情报提醒" className="monitoring-records">
          <table aria-label="情报提醒">
            <thead>
              <tr>
                <th>主题</th>
                <th>变更实体</th>
                <th>摘要</th>
                <th>发生时间</th>
                <th>状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td className="monitoring-record-name" data-label="主题">
                    {alert.topic_name}
                  </td>
                  <td className="monitoring-record-body" data-label="变更实体">
                    <strong>{alert.entity_name}</strong>
                  </td>
                  <td className="monitoring-record-body" data-label="摘要">
                    {alert.summary}
                  </td>
                  <td className="monitoring-record-meta" data-label="发生时间">
                    {formatDate(alert.occurred_at)}
                  </td>
                  <td className="monitoring-record-meta" data-label="状态">
                    <StatusBadge value={alert.read_at ? "read" : "unread"} />
                  </td>
                  <td className="monitoring-record-actions">
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title="打开实体"
                        aria-label={`打开 ${alert.entity_name}`}
                        onClick={() => onOpenEntity(alert.entity_id)}
                      >
                        <ExternalLink size={16} aria-hidden="true" />
                        <span className="monitoring-action-label">查看</span>
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        title="重放事件产生时的原始检索条件"
                        aria-label={`重放 ${alert.topic_name} 监控检索`}
                        disabled={pending.has(`replay:alert:${alert.id}`)}
                        aria-busy={pending.has(`replay:alert:${alert.id}`) || undefined}
                        onClick={() => onReplay(alert.id)}
                      >
                        <Search size={16} aria-hidden="true" />
                        <span className="monitoring-action-label">重放</span>
                      </button>
                      {!alert.read_at ? (
                        <button
                          className="icon-button"
                          type="button"
                          title="标记已读"
                          aria-label={`将 ${alert.entity_name} 提醒标记已读`}
                          disabled={pending.has(`read:${alert.id}`)}
                          onClick={() => onMarkRead(alert)}
                        >
                          <Check size={16} aria-hidden="true" />
                          <span className="monitoring-action-label">已读</span>
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <EmptyState
          title={unreadOnly ? "暂无未读提醒" : "暂无变更提醒"}
          detail={unreadOnly ? "可以取消“仅看未读”查看已读记录" : "已启用的监控主题将在数据变化时生成提醒"}
        />
      )}
    </>
  );
}
