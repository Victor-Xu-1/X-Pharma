import { Check, X } from "lucide-react";
import { EmptyState, formatDate, humanBytes, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DataExportJob } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { ExportRecordDetails } from "./ExportRecordDetails";

export function ExportTable({
  items,
  busy,
  onAction,
}: {
  items: DataExportJob[];
  busy: string;
  onAction: (job: DataExportJob, action: "approve" | "cancel") => void;
}) {
  useLocale();
  if (!items.length) return <EmptyState title={t("暂无数据导出任务")} />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel={t("数据导出任务滚动区域")}>
      <table aria-label={t("数据导出任务")}>
        <thead>
          <tr>
            <th>{t("数据集 / 任务")}</th>
            <th>{t("格式")}</th>
            <th>{t("状态")}</th>
            <th>{t("申请上限")}</th>
            <th>{t("实际记录")}</th>
            <th>{t("文件大小")}</th>
            <th>{t("申请时间")}</th>
            <th>{t("审批人")}</th>
            <th>{t("操作")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.dataset}</strong>
                <span className="cell-subtitle mono-cell">{item.id}</span>
                <ExportRecordDetails item={item} />
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
                      disabled={Boolean(busy)}
                      title={t("批准导出")}
                      aria-label={t("批准导出 {id}", { id: item.id })}
                      onClick={() => onAction(item, "approve")}
                    >
                      <Check size={17} />
                    </button>
                  ) : null}
                  {["pending_approval", "queued", "running"].includes(item.state) ? (
                    <button
                      className="icon-button danger-text"
                      type="button"
                      disabled={Boolean(busy)}
                      title={t("取消导出")}
                      aria-label={t("取消导出 {id}", { id: item.id })}
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
