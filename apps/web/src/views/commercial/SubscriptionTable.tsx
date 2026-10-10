import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialOverview } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialRecordText } from "../../lib/i18n/commercialRecordDetails";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { RecordDetails, RecordFacts, RecordList } from "./RecordDetails";

export function SubscriptionTable({ items }: { items: CommercialOverview["subscriptions"] }) {
  useLocale();
  if (!items.length) return <EmptyState title={t("暂无商业订阅")} />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel={t("商业合同与额度滚动区域")}>
      <table aria-label={t("商业合同与额度")}>
        <thead>
          <tr>
            <th>{t("客户 / 订阅")}</th>
            <th>{t("计费账户")}</th>
            <th>{t("状态")}</th>
            <th>{t("授予额度")}</th>
            <th>{t("已消耗")}</th>
            <th>{t("已预留")}</th>
            <th>{t("可用额度")}</th>
            <th>{t("今日记录")}</th>
            <th>{t("权益")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.subscription_id}>
              <td>
                <strong>{item.client_name}</strong>
                <span className="cell-subtitle mono-cell">{item.subscription_key}</span>
                <RecordDetails name={item.subscription_key}>
                  <RecordFacts
                    fields={[
                      { label: "订阅标识", value: item.subscription_id },
                      { label: "订阅开始", value: formatDate(item.starts_at, true) },
                      { label: "订阅结束", value: item.ends_at ? formatDate(item.ends_at, true) : null },
                      { label: "费率卡", value: item.rate_card_key },
                      { label: "费率卡版本", value: item.rate_card_revision },
                      { label: "活跃预留", value: item.active_reservations },
                      { label: "每日新增唯一记录", value: item.daily_usage.new_unique_record_count },
                      { label: "每日响应字节", value: item.daily_usage.response_bytes },
                      { label: "每日结果数", value: item.daily_usage.result_count },
                      { label: "每日结算数", value: item.daily_usage.settlement_count },
                    ]}
                  />
                  {item.entitlements.length ? (
                    item.entitlements.map((entitlement) => (
                      <RecordFacts
                        key={entitlement.key}
                        fields={[
                          { label: "权益键", value: entitlement.key },
                          { label: "数据域", value: <RecordList values={entitlement.data_domains} /> },
                          { label: "最大页深", value: entitlement.max_page_depth },
                          { label: "最大响应字节", value: entitlement.max_response_bytes },
                          { label: "最大结果行数", value: entitlement.max_result_rows },
                          { label: "每日唯一记录上限", value: entitlement.daily_unique_record_limit },
                          { label: "每日额度上限", value: entitlement.daily_unit_limit },
                        ]}
                      />
                    ))
                  ) : (
                    <p>{commercialRecordText("暂无权益")}</p>
                  )}
                </RecordDetails>
              </td>
              <td>
                {item.billing_account_name}
                <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
              </td>
              <td>
                <StatusBadge value={item.status} />
              </td>
              <td>{item.granted_units}</td>
              <td>{item.consumed_units}</td>
              <td>{item.reserved_units}</td>
              <td>
                <strong>{item.available_units}</strong>
              </td>
              <td>{item.daily_unique_records}</td>
              <td>{item.entitlements.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
