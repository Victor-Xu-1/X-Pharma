import { Check, X } from "lucide-react";
import { EmptyState, formatDate, humanBytes, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DataExportJob } from "../../lib/contracts/commercial";

export function ExportTable({
  items,
  busy,
  onAction,
}: {
  items: DataExportJob[];
  busy: string;
  onAction: (job: DataExportJob, action: "approve" | "cancel") => void;
}) {
  if (!items.length) return <EmptyState title="暂无数据导出任务" />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel="数据导出任务滚动区域">
      <table aria-label="数据导出任务">
        <thead>
          <tr>
            <th>数据集 / 任务</th>
            <th>格式</th>
            <th>状态</th>
            <th>申请上限</th>
            <th>实际记录</th>
            <th>文件大小</th>
            <th>申请时间</th>
            <th>审批人</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.dataset}</strong>
                <span className="cell-subtitle mono-cell">{item.id}</span>
              </td>
              <td>{item.format.toUpperCase()}</td>
              <td>
                <StatusBadge value={item.state} />
              </td>
              <td>{item.max_records}</td>
              <td>{item.record_count}</td>
              <td>{humanBytes(item.artifact_bytes)}</td>
              <td>{formatDate(item.requested_at, true)}</td>
              <td>{item.approved_by ?? "--"}</td>
              <td>
                <div className="row-actions">
                  {item.state === "pending_approval" ? (
                    <button
                      className="icon-button"
                      type="button"
                      disabled={busy === `export:${item.id}`}
                      title="批准导出"
                      aria-label={`批准导出 ${item.id}`}
                      onClick={() => onAction(item, "approve")}
                    >
                      <Check size={17} />
                    </button>
                  ) : null}
                  {["pending_approval", "queued", "running"].includes(item.state) ? (
                    <button
                      className="icon-button danger-text"
                      type="button"
                      disabled={busy === `export:${item.id}`}
                      title="取消导出"
                      aria-label={`取消导出 ${item.id}`}
                      onClick={() => onAction(item, "cancel")}
                    >
                      <X size={17} />
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
