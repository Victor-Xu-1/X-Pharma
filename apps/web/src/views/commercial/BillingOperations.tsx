import { Link2, RotateCcw, Scale } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { BillingAccount, BillingDelivery, BillingDeliveryFilter } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";

export function BillingOperations({
  accounts,
  deliveries,
  deliveryFilter,
  busy,
  onDeliveryFilter,
  onMapping,
  onReplay,
  onDispute,
}: {
  accounts: BillingAccount[];
  deliveries: BillingDelivery[];
  deliveryFilter: BillingDeliveryFilter;
  busy: string;
  onDeliveryFilter: (value: BillingDeliveryFilter) => void;
  onMapping: (account: BillingAccount) => void;
  onReplay: (delivery: BillingDelivery) => void;
  onDispute: (delivery: BillingDelivery) => void;
}) {
  useLocale();
  return (
    <div className="billing-operations">
      <section aria-labelledby="billing-accounts-title">
        <div className="billing-section-heading">
          <h2 id="billing-accounts-title">{t("计费账户映射")}</h2>
        </div>
        {accounts.length ? (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("计费账户映射滚动区域")}>
            <table aria-label={t("计费账户映射")}>
              <thead>
                <tr>
                  <th>{t("计费账户")}</th>
                  <th>{t("币种")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("Provider 客户编号")}</th>
                  <th>{t("账期单")}</th>
                  <th>{t("待开票")}</th>
                  <th>{t("发票")}</th>
                  <th>{t("更新时间")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => (
                  <tr key={account.id}>
                    <td>
                      <strong>{account.display_name}</strong>
                      <span className="cell-subtitle mono-cell">{account.account_key}</span>
                    </td>
                    <td>{account.currency}</td>
                    <td>
                      <StatusBadge value={account.status} />
                    </td>
                    <td className="mono-cell">{account.external_customer_reference_masked ?? t("未配置")}</td>
                    <td>{account.statement_count}</td>
                    <td className={account.unresolved_statement_count ? "danger-text" : ""}>
                      {account.unresolved_statement_count}
                    </td>
                    <td>{account.invoice_count}</td>
                    <td>{formatDate(account.updated_at, true)}</td>
                    <td>
                      <button
                        className="icon-button"
                        type="button"
                        disabled={Boolean(busy)}
                        title={t("配置 Provider 客户编号")}
                        aria-label={t("配置 {name} 的 Provider 客户编号", { name: account.display_name })}
                        onClick={() => onMapping(account)}
                      >
                        <Link2 size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={t("暂无计费账户")} />
        )}
      </section>
      <section aria-labelledby="billing-deliveries-title">
        <div className="billing-section-heading">
          <h2 id="billing-deliveries-title">{t("Provider 投递队列")}</h2>
          <label>
            <span>{t("投递状态")}</span>
            <select
              aria-label={t("投递状态")}
              disabled={Boolean(busy)}
              value={deliveryFilter}
              onChange={(event) => onDeliveryFilter(event.target.value as BillingDeliveryFilter)}
            >
              <option value="all">{t("全部")}</option>
              <option value="pending">{t("待处理")}</option>
              <option value="processing">{t("处理中")}</option>
              <option value="retry">{t("待重试")}</option>
              <option value="succeeded">{t("已成功")}</option>
              <option value="dead">{t("死信")}</option>
            </select>
          </label>
        </div>
        {deliveries.length ? (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("账单投递队列滚动区域")}>
            <table aria-label={t("账单投递队列")}>
              <thead>
                <tr>
                  <th>{t("账期单")}</th>
                  <th>{t("计费账户")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("尝试次数")}</th>
                  <th>{t("Provider 发票")}</th>
                  <th>{t("可执行时间")}</th>
                  <th>{t("完成时间")}</th>
                  <th>{t("最近错误")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {deliveries.map((delivery) => (
                  <tr key={delivery.event_id}>
                    <td>
                      <strong>{delivery.statement_key}</strong>
                      <span className="cell-subtitle mono-cell">{delivery.statement_id}</span>
                    </td>
                    <td>
                      {delivery.billing_account_name}
                      <span className="cell-subtitle mono-cell">{delivery.billing_account_key}</span>
                    </td>
                    <td>
                      <StatusBadge value={delivery.state} />
                    </td>
                    <td>{delivery.attempts}</td>
                    <td className="mono-cell">{delivery.external_invoice_id ?? "--"}</td>
                    <td>{formatDate(delivery.available_at, true)}</td>
                    <td>{formatDate(delivery.processed_at, true)}</td>
                    <td>
                      <span className="billing-error" title={delivery.last_error ?? undefined}>
                        {delivery.last_error ?? "--"}
                      </span>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          type="button"
                          disabled={Boolean(busy)}
                          title={t("发起计费争议")}
                          aria-label={t("对账期单 {key} 发起计费争议", { key: delivery.statement_key })}
                          onClick={() => onDispute(delivery)}
                        >
                          <Scale size={17} />
                        </button>
                        {delivery.state === "dead" && delivery.delivery_id ? (
                          <button
                            className="icon-button"
                            type="button"
                            disabled={Boolean(busy)}
                            title={t("重放死信")}
                            aria-label={t("重放账期单 {key}", { key: delivery.statement_key })}
                            onClick={() => onReplay(delivery)}
                          >
                            <RotateCcw size={17} />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={t("暂无账单投递记录")} />
        )}
      </section>
    </div>
  );
}
