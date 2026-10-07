import { Ban, Database, Plus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EnterpriseAccessWorkspace, EnterpriseOperation } from "../../lib/contracts/enterprise";
import { apiKeyScopeLabel } from "./ApiKeys";
import { ModalShell } from "./ModalShell";
import type { AccessAction, ApiKeyAction } from "./types";

export function AccessPanel({
  workspace,
  onAction,
  onApiKeyAction,
  busy,
}: {
  workspace: EnterpriseAccessWorkspace;
  onAction: (action: AccessAction) => void;
  onApiKeyAction: (action: ApiKeyAction) => void;
  busy: string;
}) {
  const now = Date.now();
  const activeHolds = workspace.legalHolds.filter((hold) => hold.status === "active");
  return (
    <div className="enterprise-access">
      <section aria-labelledby="enterprise-datasets-title">
        <header>
          <div>
            <h2 id="enterprise-datasets-title">数据集与交付授权</h2>
            <p>停用后自动入库和 Web/MCP 新查询均不能继续使用该数据集。</p>
          </div>
          <Database size={19} />
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="数据集与交付授权滚动区域">
          <table aria-label="数据集与交付授权">
            <thead>
              <tr>
                <th>数据集</th>
                <th>交付通道</th>
                <th>许可</th>
                <th>状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {workspace.datasets.map((dataset) => (
                <tr key={dataset.id}>
                  <td>
                    <strong>{dataset.display_name}</strong>
                    <span className="cell-subtitle">
                      {dataset.dataset_key} · v{dataset.version}
                    </span>
                  </td>
                  <td>
                    {dataset.permitted_channels.length ? dataset.permitted_channels.join(" / ").toUpperCase() : "--"}
                  </td>
                  <td>
                    <StatusBadge value={dataset.license_current ? "current" : "expired"} />
                    <span className="cell-subtitle">{dataset.license_policy_version}</span>
                  </td>
                  <td>
                    <StatusBadge value={dataset.active ? "active" : "disabled"} />
                  </td>
                  <td>
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      disabled={Boolean(busy)}
                      onClick={() => onAction({ kind: "dataset", dataset })}
                    >
                      {dataset.active ? "停用" : "启用"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="enterprise-sessions-title">
        <header>
          <div>
            <h2 id="enterprise-sessions-title">登录会话</h2>
            <p>可单独撤销远程会话；角色或账户状态变化会使该用户全部会话失效。</p>
          </div>
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="登录会话滚动区域">
          <table aria-label="登录会话">
            <thead>
              <tr>
                <th>用户</th>
                <th>签发</th>
                <th>到期</th>
                <th>状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {workspace.sessions.map((item) => {
                const active = !item.revoked_at && new Date(item.expires_at).getTime() > now;
                return (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.user_display_name}</strong>
                      <span className="cell-subtitle">{item.user_email}</span>
                    </td>
                    <td>{formatDate(item.issued_at, true)}</td>
                    <td>{formatDate(item.expires_at, true)}</td>
                    <td>
                      <StatusBadge
                        value={item.current ? "current" : active ? "active" : item.revoked_at ? "revoked" : "expired"}
                      />
                    </td>
                    <td>
                      <button
                        className="secondary-button compact-button"
                        type="button"
                        disabled={!active || item.current || Boolean(busy)}
                        onClick={() => onAction({ kind: "session", session: item })}
                      >
                        撤销
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="enterprise-api-keys-title">
        <header>
          <div>
            <h2 id="enterprise-api-keys-title">Agent API 密钥</h2>
            <p>完整密钥只在创建或轮换后显示一次；列表仅保留安全前缀和使用状态。</p>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={Boolean(busy)}
            onClick={() => onApiKeyAction({ kind: "create" })}
          >
            <Plus size={16} />
            新建密钥
          </button>
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="Agent API 密钥滚动区域">
          <table aria-label="Agent API 密钥">
            <thead>
              <tr>
                <th>密钥</th>
                <th>授权范围</th>
                <th>有效期</th>
                <th>商业绑定</th>
                <th>状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {workspace.apiKeyCatalog.items.length ? (
                workspace.apiKeyCatalog.items.map((apiKey) => (
                  <tr key={apiKey.id}>
                    <td>
                      <strong>{apiKey.name}</strong>
                      <span className="cell-subtitle mono-value">{apiKey.prefix}</span>
                    </td>
                    <td>
                      {apiKey.scopes.length} 项
                      <span className="cell-subtitle">{apiKey.scopes.map(apiKeyScopeLabel).join(" · ")}</span>
                    </td>
                    <td>
                      {apiKey.expires_at ? formatDate(apiKey.expires_at, true) : "未设置"}
                      <span className="cell-subtitle">
                        最近使用：{apiKey.last_used_at ? formatDate(apiKey.last_used_at, true) : "尚未使用"}
                      </span>
                    </td>
                    <td>
                      {apiKey.commercial_client_name ?? "未绑定"}
                      <span className="cell-subtitle mono-value">{apiKey.commercial_client_id ?? "--"}</span>
                    </td>
                    <td>
                      <StatusBadge value={apiKey.status} />
                    </td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          type="button"
                          title={`轮换 ${apiKey.name}`}
                          aria-label={`轮换 ${apiKey.name}`}
                          disabled={apiKey.status !== "active" || Boolean(busy)}
                          onClick={() => onApiKeyAction({ kind: "rotate", apiKey })}
                        >
                          <RotateCcw size={15} />
                        </button>
                        <button
                          className="icon-button danger-button"
                          type="button"
                          title={`撤销 ${apiKey.name}`}
                          aria-label={`撤销 ${apiKey.name}`}
                          disabled={apiKey.status !== "active" || Boolean(busy)}
                          onClick={() => onApiKeyAction({ kind: "revoke", apiKey })}
                        >
                          <Ban size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>
                    <EmptyState title="暂无 Agent API 密钥" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section aria-labelledby="enterprise-clients-title">
        <header>
          <div>
            <h2 id="enterprise-clients-title">API / MCP Clients</h2>
            <p>远程 Agent 身份与主体绑定状态。</p>
          </div>
        </header>
        <ScrollableTableRegion className="enterprise-table" ariaLabel="API 与 MCP Clients 滚动区域">
          <table aria-label="API 与 MCP Clients">
            <thead>
              <tr>
                <th>Client</th>
                <th>计费账户</th>
                <th>绑定主体</th>
                <th>状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {workspace.clients.map((client) => (
                <tr key={client.id}>
                  <td>
                    <strong>{client.display_name}</strong>
                    <span className="cell-subtitle">{client.client_key}</span>
                  </td>
                  <td className="mono-value">{client.billing_account_key ?? "--"}</td>
                  <td>{client.subjects.filter((subject) => subject.active).length}</td>
                  <td>
                    <StatusBadge value={client.active ? "active" : "disabled"} />
                  </td>
                  <td>
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      disabled={Boolean(busy)}
                      onClick={() => onAction({ kind: "client", client })}
                    >
                      {client.active ? "停用" : "启用"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section className="enterprise-lifecycle-summary" aria-labelledby="enterprise-lifecycle-title">
        <header>
          <div>
            <h2 id="enterprise-lifecycle-title">保留、Legal Hold 与合法删除</h2>
            <p>危险操作继续在经过专门影响分析的数据生命周期控制面执行。</p>
          </div>
        </header>
        <dl>
          <div>
            <dt>有效保留策略</dt>
            <dd>{workspace.retentionPolicies.filter((policy) => policy.active).length}</dd>
          </div>
          <div>
            <dt>生效 Legal Hold</dt>
            <dd>{activeHolds.length}</dd>
          </div>
        </dl>
        <a className="secondary-button" href="/workspace/internal?view=commercial">
          打开数据生命周期治理
        </a>
      </section>
    </div>
  );
}

export function AccessActionModal({
  action,
  busy,
  close,
  submit,
}: {
  action: AccessAction;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const subject =
    action.kind === "dataset"
      ? action.dataset.display_name
      : action.kind === "session"
        ? `${action.session.user_display_name} · ${formatDate(action.session.issued_at, true)}`
        : action.client.display_name;
  const title =
    action.kind === "session"
      ? "撤销登录会话"
      : action.kind === "dataset"
        ? "变更数据集状态"
        : "变更 Agent Client 状态";
  return (
    <ModalShell title={title} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const operation: EnterpriseOperation =
            action.kind === "dataset"
              ? {
                  kind: "update-dataset",
                  datasetId: action.dataset.id,
                  requestBody: {
                    expected_version: action.dataset.version,
                    active: !action.dataset.active,
                    reason: reason.trim(),
                  },
                }
              : action.kind === "session"
                ? { kind: "revoke-session", sessionId: action.session.id, requestBody: { reason: reason.trim() } }
                : {
                    kind: "update-client",
                    clientId: action.client.id,
                    requestBody: { active: !action.client.active, reason: reason.trim() },
                  };
          void submit(operation);
        }}
      >
        <p className="enterprise-modal-subject">{subject}</p>
        <label>
          变更原因
          <textarea
            required
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
            确认变更
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
