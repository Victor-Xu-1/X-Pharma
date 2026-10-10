import { EmptyState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseAuditFilters, loadEnterpriseAudit } from "../../lib/contracts/enterprise";
import { useLocale } from "../../lib/i18n";
import { enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";

export function AuditPanel({
  filters,
  draftAction,
  setDraftAction,
  setFilters,
  page,
  loading,
}: {
  filters: EnterpriseAuditFilters;
  draftAction: string;
  setDraftAction: (value: string) => void;
  setFilters: (value: EnterpriseAuditFilters) => void;
  page: Awaited<ReturnType<typeof loadEnterpriseAudit>> | undefined;
  loading: boolean;
}) {
  useLocale();
  return (
    <>
      <form
        className="enterprise-audit-filter"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters({ ...filters, cursor: undefined, action: draftAction.trim() || undefined });
        }}
      >
        <input
          value={draftAction}
          onChange={(event) => setDraftAction(event.target.value)}
          placeholder={t("按动作筛选，例如 enterprise.user.created")}
          aria-label={t("审计动作")}
        />
        <select
          value={filters.actorType ?? ""}
          onChange={(event) =>
            setFilters({
              ...filters,
              cursor: undefined,
              actorType: (event.target.value || undefined) as EnterpriseAuditFilters["actorType"],
            })
          }
          aria-label={t("操作者类型")}
        >
          <option value="">{t("全部操作者")}</option>
          <option value="user">{t("用户")}</option>
          <option value="api_key">API Key</option>
          <option value="agent">Agent</option>
        </select>
        <select
          value={filters.outcome ?? ""}
          onChange={(event) => setFilters({ ...filters, cursor: undefined, outcome: event.target.value || undefined })}
          aria-label={t("执行结果")}
        >
          <option value="">{t("全部结果")}</option>
          <option value="success">{t("成功")}</option>
          <option value="denied">{t("拒绝")}</option>
          <option value="failed">{t("失败")}</option>
        </select>
        <button className="secondary-button" type="submit" disabled={loading}>
          {t("筛选")}
        </button>
      </form>
      {loading && !page ? <Spinner label={t("正在读取审计日志")} /> : null}
      {page?.items.length ? (
        <ScrollableTableRegion className="enterprise-table" ariaLabel={t("企业审计事件滚动区域")}>
          <table aria-label={t("企业审计事件")}>
            <thead>
              <tr>
                <th>{t("时间")}</th>
                <th>{t("动作")}</th>
                <th>{t("操作者")}</th>
                <th>{t("资源")}</th>
                <th>{t("结果")}</th>
                <th>{t("请求 ID")}</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((event) => (
                <tr key={event.id}>
                  <td>{formatDate(event.occurred_at, true)}</td>
                  <td className="mono-value">{event.action}</td>
                  <td>
                    <strong>{event.actor_type}</strong>
                    <span className="cell-subtitle">{event.actor_id}</span>
                  </td>
                  <td>
                    {event.resource_type}
                    <span className="cell-subtitle">{event.resource_id ?? "--"}</span>
                  </td>
                  <td>
                    <StatusBadge value={event.outcome} />
                  </td>
                  <td className="mono-value">{event.request_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : page ? (
        <EmptyState title={t("没有符合条件的审计事件")} />
      ) : null}
      <div className="enterprise-audit-pagination">
        {filters.cursor ? (
          <button className="text-button" type="button" onClick={() => setFilters({ ...filters, cursor: undefined })}>
            {t("返回第一页")}
          </button>
        ) : null}
        {page?.next_cursor ? (
          <button
            className="secondary-button"
            type="button"
            onClick={() => setFilters({ ...filters, cursor: page.next_cursor ?? undefined })}
            disabled={loading}
          >
            {t("下一页")}
          </button>
        ) : null}
      </div>
    </>
  );
}
