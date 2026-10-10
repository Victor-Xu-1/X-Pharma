import { ShieldAlert } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialRiskEvent } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { OriginalRecordValue, RecordDetails, RecordFacts } from "./RecordDetails";
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
                <RecordDetails name={item.id}>
                  <RecordFacts
                    fields={[
                      { label: "事件标识", value: item.id },
                      { label: "客户端标识", value: item.client_id },
                      { label: "主体类型", value: item.actor_type },
                      { label: "请求标识", value: item.request_id },
                      { label: "查询摘要", value: item.query_sha256 },
                      { label: "已有唯一记录", value: item.existing_unique_records },
                      { label: "复核时间", value: item.reviewed_at ? formatDate(item.reviewed_at, true) : null },
                      { label: "复核人", value: item.reviewed_by },
                      { label: "复核说明", value: item.case_notes },
                      { label: "原始事件详情", value: <OriginalRecordValue value={item.details} /> },
                    ]}
                  />
                </RecordDetails>
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
