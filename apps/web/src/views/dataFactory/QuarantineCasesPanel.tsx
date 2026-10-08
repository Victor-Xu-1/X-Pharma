import { Shield, ShieldAlert } from "lucide-react";
import { formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { SourceVersionQuarantineCaseRead } from "../../lib/generated";
import { quarantineStatusLabel } from "../../lib/quarantinePresentation";
import type { User } from "../../lib/types";
import { FactoryDetailsPanel } from "./FactoryDetailsPanel";

const activeStatuses = new Set(["pending_review", "held", "rescan_requested"]);

export function QuarantineCasesPanel({
  items,
  role,
  stale,
  onOpen,
}: {
  items: readonly SourceVersionQuarantineCaseRead[];
  role: User["role"];
  stale: boolean;
  onOpen: (sourceVersionId: string) => void;
}) {
  const activeCount = items.filter((item) => activeStatuses.has(item.quarantine_status)).length;
  return (
    <FactoryDetailsPanel
      title="恶意文件隔离"
      className="quarantine-panel"
      reveal={activeCount > 0}
      summary={
        <span
          className={activeCount > 0 ? "quarantine-count" : undefined}
          role="status"
          aria-label={`${stale ? "上次读取 · " : ""}${activeCount} 个待处置案件`}
        >
          {stale ? "上次读取 · " : ""}
          {activeCount} 待处置
        </span>
      }
    >
      <p>安全扫描命中的源版本不会进入解析、AI 治理或检索发布，必须经过受审计的人工处置。</p>
      {items.length ? (
        <ScrollableTableRegion ariaLabel="恶意文件隔离案件" className="quarantine-table">
          <table>
            <thead>
              <tr>
                <th>隔离文件</th>
                <th>威胁</th>
                <th>处置状态</th>
                <th>决策版本</th>
                <th>最近变更</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.source_version_id}>
                  <td data-label="隔离文件">
                    <span className="quarantine-file">
                      <strong>{item.file_name}</strong>
                      <small className="mono-cell">{item.logical_path}</small>
                    </span>
                  </td>
                  <td data-label="威胁" className="quarantine-threat">
                    {item.threat_name ?? "未披露签名"}
                  </td>
                  <td data-label="处置状态">
                    <StatusBadge value={item.quarantine_status} label={quarantineStatusLabel(item.quarantine_status)} />
                  </td>
                  <td data-label="决策版本">v{item.quarantine_version}</td>
                  <td data-label="最近变更">{formatDate(item.updated_at, true)}</td>
                  <td data-label="操作">
                    <button className="secondary-button" type="button" onClick={() => onOpen(item.source_version_id)}>
                      <ShieldAlert size={15} aria-hidden="true" />
                      {role === "admin" && activeStatuses.has(item.quarantine_status) ? "处置" : "查看"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <div className="factory-run-empty">
          <Shield size={20} aria-hidden="true" />
          <span>
            <strong>当前没有隔离案件</strong>
            <small>扫描命中后，文件会自动阻断并显示在这里。</small>
          </span>
        </div>
      )}
    </FactoryDetailsPanel>
  );
}
