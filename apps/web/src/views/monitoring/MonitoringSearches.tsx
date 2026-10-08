import { LockKeyhole, Pencil, Search, Share2 } from "lucide-react";
import { EmptyState, formatDate } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { SavedSearch } from "../../lib/contracts/monitoring";
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
  if (!searches.length) return <EmptyState title="暂无已保存检索" detail="在情报检索页保存常用条件" />;
  return (
    <ScrollableTableRegion ariaLabel="已保存检索" className="monitoring-records">
      <table aria-label="已保存检索">
        <thead>
          <tr>
            <th>名称</th>
            <th>查询</th>
            <th>类型</th>
            <th>共享范围</th>
            <th>版本</th>
            <th>更新时间</th>
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {searches.map((saved) => {
            const summary = savedSearchSummary(saved);
            const replaying = pending.has(`replay:saved:${saved.id}`);
            const busy = replaying || pending.has(`saved:${saved.id}`);
            return (
              <tr key={saved.id}>
                <td className="monitoring-record-name" data-label="名称">
                  <strong>{saved.name}</strong>
                  {saved.description ? (
                    <details className="monitoring-record-description">
                      <summary>业务说明</summary>
                      <p>{saved.description}</p>
                    </details>
                  ) : null}
                </td>
                <td className="monitoring-record-body" data-label="查询">
                  {summary.query}
                  {summary.conditions.length ? (
                    <small className="cell-subtitle" title={summary.conditions.join(" · ")}>
                      条件：{summary.conditions.join(" · ")}
                    </small>
                  ) : null}
                </td>
                <td className="monitoring-record-meta" data-label="类型">
                  {summary.type}
                  <small className="cell-subtitle">{summary.view}</small>
                </td>
                <td className="monitoring-record-meta" data-label="共享范围">
                  {saved.visibility === "tenant" ? "企业共享" : "仅自己"}
                  {saved.owner_user_id !== userId ? <small className="cell-subtitle">共享给你的只读检索</small> : null}
                </td>
                <td className="monitoring-record-meta" data-label="版本">
                  v{saved.query_version}
                </td>
                <td className="monitoring-record-meta" data-label="更新时间">
                  {formatDate(saved.updated_at)}
                </td>
                <td className="monitoring-record-actions">
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      type="button"
                      title={replaying ? "正在核验当前检索与访问权限" : "运行已保存检索"}
                      aria-label={`运行 ${saved.name}`}
                      disabled={busy}
                      aria-busy={replaying || undefined}
                      onClick={() => onReplay(saved.id)}
                    >
                      <Search size={16} aria-hidden="true" />
                      <span className="monitoring-action-label">运行</span>
                    </button>
                    {saved.owner_user_id === userId ? (
                      <>
                        <button
                          className="icon-button"
                          type="button"
                          title="编辑名称与业务说明"
                          aria-label={`编辑 ${saved.name}`}
                          disabled={busy}
                          onClick={() => onEdit(saved)}
                        >
                          <Pencil size={16} aria-hidden="true" />
                          <span className="monitoring-action-label">编辑</span>
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          title={saved.visibility === "tenant" ? "撤回企业共享" : "共享给企业成员"}
                          aria-label={
                            saved.visibility === "tenant" ? `将 ${saved.name} 设为私有` : `共享 ${saved.name}`
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
                            {saved.visibility === "tenant" ? "撤回共享" : "共享"}
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
