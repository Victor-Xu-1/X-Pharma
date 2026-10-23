import { Scale } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { BillingDispute, BillingDisputeFilter } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { RecordDetails, RecordFacts } from "./RecordDetails";

export function BillingDisputeTable({
  items,
  filter,
  busy,
  onFilter,
  onAction,
}: {
  items: BillingDispute[];
  filter: BillingDisputeFilter;
  busy: string;
  onFilter: (value: BillingDisputeFilter) => void;
  onAction: (dispute: BillingDispute) => void;
}) {
  useLocale();
  return (
    <div className="billing-operations">
      <div className="billing-section-heading">
        <h2>{t("计费争议案件")}</h2>
        <label>
          <span>{t("案件状态")}</span>
          <select
            aria-label={t("争议状态")}
            disabled={Boolean(busy)}
            value={filter}
            onChange={(event) => onFilter(event.target.value as BillingDisputeFilter)}
          >
            <option value="all">{t("全部")}</option>
            <option value="open">{t("待受理")}</option>
            <option value="investigating">{t("调查中")}</option>
            <option value="resolved">{t("已解决")}</option>
            <option value="rejected">{t("已驳回")}</option>
            <option value="cancelled">{t("已取消")}</option>
          </select>
        </label>
      </div>
      {items.length ? (
        <ScrollableTableRegion className="commercial-table" ariaLabel={t("计费争议滚动区域")}>
          <table aria-label={t("计费争议")}>
            <thead>
              <tr>
                <th>{t("案件 / 主题")}</th>
                <th>{t("计费账户")}</th>
                <th>{t("账期单")}</th>
                <th>{t("争议额度")}</th>
                <th>{t("类别")}</th>
                <th>{t("状态")}</th>
                <th>{t("负责人")}</th>
                <th>SLA</th>
                <th>{t("操作")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.subject}</strong>
                    <span className="cell-subtitle mono-cell">{item.dispute_key}</span>
                    <RecordDetails name={item.dispute_key}>
                      <RecordFacts
                        fields={[
                          { label: "标识", value: item.id },
                          { label: "版本", value: item.version },
                          { label: "说明", value: item.description },
                          { label: "开案时间", value: formatDate(item.opened_at, true) },
                          { label: "开案人", value: item.opened_by },
                          { label: "账期单标识", value: item.statement_id },
                          { label: "订阅标识", value: item.subscription_id },
                          { label: "账户标识", value: item.billing_account_id },
                          { label: "发票关联标识", value: item.invoice_reference_id },
                          { label: "外部发票标识", value: item.external_invoice_id },
                          { label: "解决时间", value: item.resolved_at ? formatDate(item.resolved_at, true) : null },
                          { label: "解决人", value: item.resolved_by },
                          { label: "解决代码", value: item.resolution_code },
                          { label: "解决说明", value: item.resolution_notes },
                          { label: "账本调整键", value: item.resolution_adjustment_key },
                        ]}
                      />
                    </RecordDetails>
                  </td>
                  <td>
                    {item.billing_account_name}
                    <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
                  </td>
                  <td className="mono-cell">{item.statement_key}</td>
                  <td>{item.disputed_units}</td>
                  <td>{item.category}</td>
                  <td>
                    <StatusBadge value={item.status} />
                  </td>
                  <td>{item.assigned_to ?? t("未分配")}</td>
                  <td className={item.overdue ? "danger-text" : ""}>{formatDate(item.due_at, true)}</td>
                  <td>
                    {["resolved", "rejected", "cancelled"].includes(item.status) ? (
                      "--"
                    ) : (
                      <button
                        className="icon-button"
                        type="button"
                        disabled={Boolean(busy)}
                        title={t("处理计费争议")}
                        aria-label={t("处理计费争议 {key}", { key: item.dispute_key })}
                        onClick={() => onAction(item)}
                      >
                        <Scale size={17} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <EmptyState title={t("暂无计费争议")} />
      )}
    </div>
  );
}
