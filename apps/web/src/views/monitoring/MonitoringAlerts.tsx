import { Check, ExternalLink, Search } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { MonitoringAlert } from "../../lib/contracts/monitoring";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { monitoringMessages } from "../../lib/i18n/monitoring";

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
  const text = useMessages(monitoringMessages);
  return (
    <>
      <div className="section-toolbar">
        <label className="check-control">
          <input type="checkbox" checked={unreadOnly} onChange={(event) => onUnreadOnlyChange(event.target.checked)} />
          {text("仅看未读")}
        </label>
        <span>
          {text("当前结果中 {count} 条未读", {
            count: new Intl.NumberFormat(formattingLocale()).format(alerts.filter((item) => !item.read_at).length),
          })}
        </span>
      </div>
      {alerts.length ? (
        <ScrollableTableRegion ariaLabel={text("情报提醒")} className="monitoring-records">
          <table aria-label={text("情报提醒")}>
            <thead>
              <tr>
                <th>{text("主题")}</th>
                <th>{text("变更实体")}</th>
                <th>{text("摘要")}</th>
                <th>{text("发生时间")}</th>
                <th>{text("状态")}</th>
                <th aria-label={text("操作")} />
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td className="monitoring-record-name" data-label={text("主题")}>
                    {alert.topic_name}
                  </td>
                  <td className="monitoring-record-body" data-label={text("变更实体")}>
                    <strong>{alert.entity_name}</strong>
                  </td>
                  <td className="monitoring-record-body" data-label={text("摘要")}>
                    {alert.summary}
                  </td>
                  <td className="monitoring-record-meta" data-label={text("发生时间")}>
                    {formatDate(alert.occurred_at)}
                  </td>
                  <td className="monitoring-record-meta" data-label={text("状态")}>
                    <StatusBadge
                      value={alert.read_at ? "read" : "unread"}
                      label={alert.read_at ? text("已读") : text("未读")}
                    />
                  </td>
                  <td className="monitoring-record-actions">
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title={text("打开实体")}
                        aria-label={text("打开 {name}", { name: alert.entity_name })}
                        onClick={() => onOpenEntity(alert.entity_id)}
                      >
                        <ExternalLink size={16} aria-hidden="true" />
                        <span className="monitoring-action-label">{text("查看")}</span>
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        title={text("重放事件产生时的原始检索条件")}
                        aria-label={text("重放 {name} 监控检索", { name: alert.topic_name })}
                        disabled={pending.has(`replay:alert:${alert.id}`)}
                        aria-busy={pending.has(`replay:alert:${alert.id}`) || undefined}
                        onClick={() => onReplay(alert.id)}
                      >
                        <Search size={16} aria-hidden="true" />
                        <span className="monitoring-action-label">{text("重放")}</span>
                      </button>
                      {!alert.read_at ? (
                        <button
                          className="icon-button"
                          type="button"
                          title={text("标记已读")}
                          aria-label={text("将 {name} 提醒标记已读", { name: alert.entity_name })}
                          disabled={pending.has(`read:${alert.id}`)}
                          onClick={() => onMarkRead(alert)}
                        >
                          <Check size={16} aria-hidden="true" />
                          <span className="monitoring-action-label">{text("已读")}</span>
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
          title={unreadOnly ? text("暂无未读提醒") : text("暂无变更提醒")}
          detail={unreadOnly ? text("可以取消“仅看未读”查看已读记录") : text("已启用的监控主题将在数据变化时生成提醒")}
        />
      )}
    </>
  );
}
