import { Link2, RotateCcw, Scale } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import type { BillingAccount, BillingDelivery, BillingDeliveryFilter } from "../../lib/contracts/commercial";

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
  return (
    <div className="billing-operations">
      <section aria-labelledby="billing-accounts-title">
        <div className="billing-section-heading">
          <h2 id="billing-accounts-title">计费账户映射</h2>
        </div>
        <div className="table-frame commercial-table">
          <table>
            <thead>
              <tr>
                <th>计费账户</th>
                <th>币种</th>
                <th>状态</th>
                <th>Provider 客户编号</th>
                <th>账期单</th>
                <th>待开票</th>
                <th>发票</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {!accounts.length ? (
                <tr>
                  <td colSpan={9}>
                    <EmptyState title="暂无计费账户" />
                  </td>
                </tr>
              ) : null}
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
                  <td className="mono-cell">{account.external_customer_reference_masked ?? "未配置"}</td>
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
                      disabled={busy === `mapping:${account.id}`}
                      title="配置 Provider 客户编号"
                      aria-label={`配置 ${account.display_name} 的 Provider 客户编号`}
                      onClick={() => onMapping(account)}
                    >
                      <Link2 size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-labelledby="billing-deliveries-title">
        <div className="billing-section-heading">
          <h2 id="billing-deliveries-title">Provider 投递队列</h2>
          <label>
            <span>投递状态</span>
            <select
              aria-label="投递状态"
              value={deliveryFilter}
              onChange={(event) => onDeliveryFilter(event.target.value as BillingDeliveryFilter)}
            >
              <option value="all">全部</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="retry">待重试</option>
              <option value="succeeded">已成功</option>
              <option value="dead">死信</option>
            </select>
          </label>
        </div>
        <div className="table-frame commercial-table">
          <table>
            <thead>
              <tr>
                <th>账期单</th>
                <th>计费账户</th>
                <th>状态</th>
                <th>尝试次数</th>
                <th>Provider 发票</th>
                <th>可执行时间</th>
                <th>完成时间</th>
                <th>最近错误</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {!deliveries.length ? (
                <tr>
                  <td colSpan={9}>
                    <EmptyState title="暂无账单投递记录" />
                  </td>
                </tr>
              ) : null}
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
                        title="发起计费争议"
                        aria-label={`对账期单 ${delivery.statement_key} 发起计费争议`}
                        onClick={() => onDispute(delivery)}
                      >
                        <Scale size={17} />
                      </button>
                      {delivery.state === "dead" && delivery.delivery_id ? (
                        <button
                          className="icon-button"
                          type="button"
                          disabled={busy === `replay:${delivery.delivery_id}`}
                          title="重放死信"
                          aria-label={`重放账期单 ${delivery.statement_key}`}
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
        </div>
      </section>
    </div>
  );
}
