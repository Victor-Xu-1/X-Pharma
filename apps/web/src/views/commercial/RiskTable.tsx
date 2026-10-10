import { ShieldAlert } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialRiskEvent } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import type { RiskAction } from "./types";

export function RiskTable({
  items,
  busy,
  onAction,
}: {
  items: CommercialRiskEvent[];
  busy: string;
  onAction: (action: RiskAction) => void;
}) {
  useLocale();
  if (!items.length) return <EmptyState title={t("暂无商业风险事件")} />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel={t("商业风险事件滚动区域")}>
      <table aria-label={t("商业风险事件")}>
        <thead>
          <tr>
            <th>{t("客户端 / 主体")}</th>
            <th>{t("拒绝原因")}</th>
            <th>{t("权益 / 阶段")}</th>
            <th>{t("深度")}</th>
            <th>{t("申请记录")}</th>
            <th>{t("累计唯一记录")}</th>
            <th>{t("发生时间")}</th>
            <th>{t("处置状态")}</th>
            <th>{t("操作")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.client_name}</strong>
                <span className="cell-subtitle mono-cell">{item.subject_id}</span>
              </td>
              <td>
                <span className="risk-reason">{item.reason_code}</span>
              </td>
              <td>
                {item.entitlement_key}
                <span className="cell-subtitle">{item.phase}</span>
              </td>
              <td>{item.page_depth}</td>
              <td>{item.requested_records}</td>
              <td>{item.projected_unique_records}</td>
              <td>{formatDate(item.occurred_at, true)}</td>
              <td>
                <StatusBadge value={item.case_status} />
              </td>
              <td>
                {item.case_status === "resolved" || item.case_status === "dismissed" ? (
                  "--"
                ) : (
                  <button
                    className="icon-button"
                    type="button"
                    disabled={Boolean(busy)}
                    title={t("处置风险事件")}
                    aria-label={t("处置风险事件 {name}", { name: item.client_name })}
                    onClick={() =>
                      onAction({ event: item, status: item.case_status === "open" ? "acknowledged" : "resolved" })
                    }
                  >
                    <ShieldAlert size={17} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
