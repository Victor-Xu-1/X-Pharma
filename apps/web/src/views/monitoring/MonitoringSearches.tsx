import { LockKeyhole, Pencil, Search, Share2 } from "lucide-react";
import { EmptyState, formatDate } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { SavedSearch } from "../../lib/contracts/monitoring";
import { useMessages } from "../../lib/i18n";
import { monitoringMessages } from "../../lib/i18n/monitoring";
import { MonitoringConditions } from "./MonitoringConditions";
import { savedSearchSummary } from "./savedSearchPresentation";

export function MonitoringSearches({
  searches,
  userId,
  pending,
  onReplay,
  onEdit,
  onVisibilityChange,
}: {
  searches: SavedSearch[];
  userId: string;
  pending: ReadonlySet<string>;
  onReplay: (id: string) => void;
  onEdit: (saved: SavedSearch) => void;
  onVisibilityChange: (saved: SavedSearch) => void;
}) {
  const text = useMessages(monitoringMessages);
  if (!searches.length) return <EmptyState title={text("暂无已保存检索")} detail={text("在情报检索页保存常用条件")} />;
  return (
    <ScrollableTableRegion ariaLabel={text("已保存检索")} className="monitoring-records">
      <table aria-label={text("已保存检索")}>
        <thead>
          <tr>
            <th>{text("名称")}</th>
            <th>{text("查询")}</th>
            <th>{text("类型")}</th>
            <th>{text("共享范围")}</th>
            <th>{text("版本")}</th>
            <th>{text("更新时间")}</th>
            <th aria-label={text("操作")} />
          </tr>
        </thead>
        <tbody>
          {searches.map((saved) => {
            const summary = savedSearchSummary(saved);
            const replaying = pending.has(`replay:saved:${saved.id}`);
            const busy = replaying || pending.has(`saved:${saved.id}`);
            return (
              <tr key={saved.id}>
                <td className="monitoring-record-name" data-label={text("名称")}>
                  <strong>{saved.name}</strong>
                  {saved.description ? (
                    <details className="monitoring-record-description">
                      <summary>{text("业务说明")}</summary>
                      <p>{saved.description}</p>
                    </details>
                  ) : null}
                </td>
                <td className="monitoring-record-body" data-label={text("查询")}>
                  {summary.query}
                  <MonitoringConditions conditions={summary.conditions} />
                </td>
                <td className="monitoring-record-meta" data-label={text("类型")}>
                  {summary.type}
                  <small className="cell-subtitle">{summary.view}</small>
                </td>
                <td className="monitoring-record-meta" data-label={text("共享范围")}>
                  {saved.visibility === "tenant" ? text("企业共享") : text("仅自己")}
                  {saved.owner_user_id !== userId ? (
                    <small className="cell-subtitle">{text("共享给你的只读检索")}</small>
                  ) : null}
                </td>
                <td className="monitoring-record-meta" data-label={text("版本")}>
                  v{saved.query_version}
                </td>
                <td className="monitoring-record-meta" data-label={text("更新时间")}>
                  {formatDate(saved.updated_at)}
                </td>
                <td className="monitoring-record-actions">
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      type="button"
                      title={replaying ? text("正在核验当前检索与访问权限") : text("运行已保存检索")}
                      aria-label={text("运行 {name}", { name: saved.name })}
                      disabled={busy}
                      aria-busy={replaying || undefined}
                      onClick={() => onReplay(saved.id)}
                    >
                      <Search size={16} aria-hidden="true" />
                      <span className="monitoring-action-label">{text("运行")}</span>
                    </button>
                    {saved.owner_user_id === userId ? (
                      <>
                        <button
                          className="icon-button"
                          type="button"
                          title={text("编辑名称与业务说明")}
                          aria-label={text("编辑 {name}", { name: saved.name })}
                          disabled={busy}
                          onClick={() => onEdit(saved)}
                        >
                          <Pencil size={16} aria-hidden="true" />
                          <span className="monitoring-action-label">{text("编辑")}</span>
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          title={saved.visibility === "tenant" ? text("撤回企业共享") : text("共享给企业成员")}
                          aria-label={
                            saved.visibility === "tenant"
                              ? text("将 {name} 设为私有", { name: saved.name })
                              : text("共享 {name}", { name: saved.name })
                          }
                          disabled={busy}
                          onClick={() => onVisibilityChange(saved)}
                        >
                          {saved.visibility === "tenant" ? (
                            <LockKeyhole size={16} aria-hidden="true" />
                          ) : (
                            <Share2 size={16} aria-hidden="true" />
                          )}
                          <span className="monitoring-action-label">
                            {saved.visibility === "tenant" ? text("撤回共享") : text("共享")}
                          </span>
                        </button>
                      </>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
