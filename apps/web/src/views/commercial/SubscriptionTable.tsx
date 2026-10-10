import { EmptyState, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialOverview } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";

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
