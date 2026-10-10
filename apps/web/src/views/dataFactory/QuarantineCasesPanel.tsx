import { Shield, ShieldAlert } from "lucide-react";
import { formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { SourceVersionQuarantineCaseRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { quarantineStatusLabel } from "../../lib/quarantinePresentation";
import type { User } from "../../lib/types";
import { FactoryDetailsPanel } from "./FactoryDetailsPanel";

export const activeQuarantineStatuses: ReadonlySet<string> = new Set(["pending_review", "held", "rescan_requested"]);

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
  useLocale();
  const activeCount = items.filter((item) => activeQuarantineStatuses.has(item.quarantine_status)).length;
  return (
    <FactoryDetailsPanel
      title={t("恶意文件隔离")}
      className="quarantine-panel"
      reveal={activeCount > 0}
      summary={
        <span
          className={activeCount > 0 ? "quarantine-count" : undefined}
          role="status"
          aria-label={`${stale ? t("上次读取 · ") : ""}${t("{count} 个待处置案件", { count: activeCount })}`}
        >
          {stale ? t("上次读取 · ") : ""}
          {t("{count} 待处置", { count: activeCount })}
        </span>
      }
    >
      <p>{t("安全扫描命中的源版本不会进入解析、AI 治理或检索发布，必须经过受审计的人工处置。")}</p>
      {items.length ? (
        <ScrollableTableRegion ariaLabel={t("恶意文件隔离案件")} className="quarantine-table">
          <table>
            <thead>
              <tr>
                <th>{t("隔离文件")}</th>
                <th>{t("威胁")}</th>
                <th>{t("处置状态")}</th>
                <th>{t("决策版本")}</th>
                <th>{t("最近变更")}</th>
                <th aria-label={t("操作")} />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.source_version_id}>
                  <td data-label={t("隔离文件")}>
                    <span className="quarantine-file">
                      <strong>{item.file_name}</strong>
                      <small className="mono-cell">{item.logical_path}</small>
                    </span>
                  </td>
                  <td data-label={t("威胁")} className="quarantine-threat">
                    {item.threat_name ?? t("未披露签名")}
                  </td>
                  <td data-label={t("处置状态")}>
                    <StatusBadge value={item.quarantine_status} label={quarantineStatusLabel(item.quarantine_status)} />
                  </td>
                  <td data-label={t("决策版本")}>v{item.quarantine_version}</td>
                  <td data-label={t("最近变更")}>{formatDate(item.updated_at, true)}</td>
                  <td data-label={t("操作")}>
                    <button className="secondary-button" type="button" onClick={() => onOpen(item.source_version_id)}>
                      <ShieldAlert size={15} aria-hidden="true" />
                      {t(role === "admin" && activeQuarantineStatuses.has(item.quarantine_status) ? "处置" : "查看")}
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
            <strong>{t("当前没有隔离案件")}</strong>
            <small>{t("扫描命中后，文件会自动阻断并显示在这里。")}</small>
          </span>
        </div>
      )}
    </FactoryDetailsPanel>
  );
}
