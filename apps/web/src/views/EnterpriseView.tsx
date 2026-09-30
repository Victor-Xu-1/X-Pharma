import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  BrainCircuit,
  Copy,
  Database,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Star,
  TestTube2,
  UserRoundCog,
  UsersRound,
  X,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import {
  type EnterpriseApiKey,
  type EnterpriseApiKeyCatalog,
  type EnterpriseApiKeyOperation,
  type EnterpriseApiKeySecret,
  type EnterpriseAuditFilters,
  type EnterpriseClient,
  type EnterpriseDataset,
  type EnterpriseGroup,
  type EnterpriseLLMProvider,
  type EnterpriseLLMProviderOperation,
  type EnterpriseOperation,
  type EnterpriseSession,
  type EnterpriseUser,
  enterpriseKeys,
  executeEnterpriseApiKeyOperation,
  executeEnterpriseLLMProviderOperation,
  executeEnterpriseOperation,
  loadEnterpriseAudit,
  loadEnterpriseWorkspace,
} from "../lib/contracts/enterprise";
import type { AuthMode } from "../lib/contracts/session";
import type { User, UserRole } from "../lib/types";

type EnterpriseTab = "overview" | "users" | "groups" | "access" | "models" | "platform" | "audit";
type UserAction = { user: EnterpriseUser; kind: "role" | "status" };
type GroupAction = { group: EnterpriseGroup; kind: "edit" | "members" };
type AccessAction =
  | { kind: "dataset"; dataset: EnterpriseDataset }
  | { kind: "session"; session: EnterpriseSession }
  | { kind: "client"; client: EnterpriseClient };
type ApiKeyAction = { kind: "create" } | { kind: "rotate" | "revoke"; apiKey: EnterpriseApiKey };
type LLMAction = { kind: "create" } | { kind: "edit" | "primary"; provider: EnterpriseLLMProvider };
type LLMProviderPreset = "mimo" | "glm";

const llmProviderPresets: Record<
  LLMProviderPreset,
  {
    name: string;
    baseUrl: string;
    model: string;
    attempts: number;
  }
> = {
  mimo: {
    name: "mimo",
    baseUrl: "https://token-plan-cn.xiaomimimo.com/v1",
    model: "mimo-v2.5",
    attempts: 2,
  },
  glm: {
    name: "glm",
    baseUrl: "https://chatapi.weixin.qq.com/openai/v1",
    model: "GLM-5.2",
    attempts: 1,
  },
};

const roleLabels: Record<UserRole, string> = { admin: "管理员", analyst: "分析师", viewer: "浏览者" };

const enterpriseTabs: Array<ResearchTabOption<EnterpriseTab>> = [
  { key: "overview", label: "租户概况" },
  { key: "users", label: "用户与角色" },
  { key: "groups", label: "用户组" },
  { key: "access", label: "访问与生命周期" },
  { key: "models", label: "模型设置" },
  { key: "platform", label: "平台运营" },
  { key: "audit", label: "审计日志" },
];

export function EnterpriseView({ user, authMode }: { user: User; authMode: AuthMode }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<EnterpriseTab>("overview");
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [createGroupOpen, setCreateGroupOpen] = useState(false);
  const [userAction, setUserAction] = useState<UserAction | null>(null);
  const [groupAction, setGroupAction] = useState<GroupAction | null>(null);
  const [accessAction, setAccessAction] = useState<AccessAction | null>(null);
  const [apiKeyAction, setApiKeyAction] = useState<ApiKeyAction | null>(null);
  const [apiKeySecret, setApiKeySecret] = useState<EnterpriseApiKeySecret | null>(null);
  const [llmAction, setLlmAction] = useState<LLMAction | null>(null);
  const [actionError, setActionError] = useState("");
  const [auditFilters, setAuditFilters] = useState<EnterpriseAuditFilters>({});
  const [auditDraftAction, setAuditDraftAction] = useState("");

  const workspaceQuery = useQuery({
    queryKey: enterpriseKeys.workspace,
    queryFn: ({ signal }) => loadEnterpriseWorkspace(signal),
  });
  const auditQuery = useQuery({
    queryKey: enterpriseKeys.audit(auditFilters),
    queryFn: ({ signal }) => loadEnterpriseAudit(auditFilters, signal),
    enabled: tab === "audit",
    placeholderData: (previous) => previous,
  });
  const operationMutation = useMutation({
    mutationFn: ({ operation }: { busyKey: string; operation: EnterpriseOperation }) =>
      executeEnterpriseOperation(operation),
    retry: false,
  });
  const apiKeyMutation = useMutation({
    mutationFn: ({ operation }: { busyKey: string; operation: EnterpriseApiKeyOperation }) =>
      executeEnterpriseApiKeyOperation(operation),
    retry: false,
  });
  const llmMutation = useMutation({
    mutationFn: ({ operation }: { busyKey: string; operation: EnterpriseLLMProviderOperation }) =>
      executeEnterpriseLLMProviderOperation(operation),
    retry: false,
  });
  const workspace = workspaceQuery.data;
  const busy = operationMutation.isPending
    ? (operationMutation.variables?.busyKey ?? "operation")
    : apiKeyMutation.isPending
      ? (apiKeyMutation.variables?.busyKey ?? "api-key")
      : llmMutation.isPending
        ? (llmMutation.variables?.busyKey ?? "llm-provider")
        : "";

  async function runOperation(busyKey: string, operation: EnterpriseOperation, fallback: string): Promise<boolean> {
    setActionError("");
    try {
      await operationMutation.mutateAsync({ busyKey, operation });
      await queryClient.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" });
      return true;
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : fallback);
      return false;
    }
  }

  async function runApiKeyOperation(
    busyKey: string,
    operation: EnterpriseApiKeyOperation,
    fallback: string,
  ): Promise<EnterpriseApiKey | EnterpriseApiKeySecret | null> {
    setActionError("");
    try {
      const result = await apiKeyMutation.mutateAsync({ busyKey, operation });
      await queryClient.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" });
      return result;
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : fallback);
      return null;
    }
  }

  async function runLlmOperation(
    busyKey: string,
    operation: EnterpriseLLMProviderOperation,
    fallback: string,
  ): Promise<boolean> {
    setActionError("");
    try {
      await llmMutation.mutateAsync({ busyKey, operation });
      await queryClient.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" });
      return true;
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : fallback);
      return false;
    }
  }

  const queryError = workspaceQuery.error ?? auditQuery.error;
  const visibleError =
    actionError || (queryError instanceof Error ? queryError.message : queryError ? "企业管理数据加载失败" : "");
  if (!workspace && workspaceQuery.isPending) return <Spinner label="正在读取企业管理数据" />;
  if (!workspace) return <ErrorState message={visibleError || "企业管理数据加载失败"} retry={workspaceQuery.refetch} />;

  return (
    <section className="enterprise-workbench">
      <div className="enterprise-toolbar">
        <span>{workspace.overview.tenant.name}</span>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void queryClient.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" })}
          disabled={Boolean(busy) || workspaceQuery.isFetching}
        >
          <RefreshCw size={16} />
          刷新
        </button>
      </div>
      {visibleError ? (
        <p className="inline-error" role="alert">
          {visibleError}
        </p>
      ) : null}
      <ResearchTabList
        tabs={enterpriseTabs}
        activeTab={tab}
        onChange={setTab}
        ariaLabel="企业管理视图"
        idPrefix="enterprise"
      />

      <div id={`enterprise-panel-${tab}`} role="tabpanel" aria-labelledby={`enterprise-tab-${tab}`}>
        {tab === "overview" ? <EnterpriseOverview workspace={workspace} /> : null}
        {tab === "users" ? (
          <UsersPanel
            users={workspace.users}
            currentUserId={user.id}
            busy={busy}
            onCreate={() => setCreateUserOpen(true)}
            onAction={setUserAction}
          />
        ) : null}
        {tab === "groups" ? (
          <GroupsPanel
            groups={workspace.groups}
            busy={busy}
            onCreate={() => setCreateGroupOpen(true)}
            onAction={setGroupAction}
          />
        ) : null}
        {tab === "access" ? (
          <AccessPanel workspace={workspace} onAction={setAccessAction} onApiKeyAction={setApiKeyAction} busy={busy} />
        ) : null}
        {tab === "models" ? (
          <LLMProvidersPanel
            providers={workspace.llmProviders}
            busy={busy}
            onCreate={() => setLlmAction({ kind: "create" })}
            onEdit={(provider) => setLlmAction({ kind: "edit", provider })}
            onPrimary={(provider) => setLlmAction({ kind: "primary", provider })}
            onTest={(provider) =>
              void runLlmOperation(
                `llm:test:${provider.id}`,
                { kind: "test-llm-provider", providerId: provider.id },
                "模型连接测试失败",
              )
            }
          />
        ) : null}
        {tab === "platform" ? <PlatformOperationsPanel workspace={workspace} /> : null}
        {tab === "audit" ? (
          <AuditPanel
            filters={auditFilters}
            draftAction={auditDraftAction}
            setDraftAction={setAuditDraftAction}
            setFilters={setAuditFilters}
            page={auditQuery.data}
            loading={auditQuery.isFetching}
          />
        ) : null}
      </div>

      {createUserOpen ? (
        <CreateUserModal
          authMode={authMode}
          busy={Boolean(busy)}
          close={() => setCreateUserOpen(false)}
          submit={async (operation) => {
            if (await runOperation("user:create", operation, "用户创建失败")) setCreateUserOpen(false);
          }}
        />
      ) : null}
      {userAction ? (
        <UserActionModal
          action={userAction}
          busy={Boolean(busy)}
          close={() => setUserAction(null)}
          submit={async (operation) => {
            if (await runOperation(`user:${userAction.user.id}`, operation, "用户更新失败")) setUserAction(null);
          }}
        />
      ) : null}
      {createGroupOpen ? (
        <CreateGroupModal
          busy={Boolean(busy)}
          close={() => setCreateGroupOpen(false)}
          submit={async (operation) => {
            if (await runOperation("group:create", operation, "用户组创建失败")) setCreateGroupOpen(false);
          }}
        />
      ) : null}
      {groupAction ? (
        <GroupActionModal
          action={groupAction}
          users={workspace.users}
          busy={Boolean(busy)}
          close={() => setGroupAction(null)}
          submit={async (operation) => {
            if (await runOperation(`group:${groupAction.group.id}`, operation, "用户组更新失败")) {
              setGroupAction(null);
            }
          }}
        />
      ) : null}
      {accessAction ? (
        <AccessActionModal
          action={accessAction}
          busy={Boolean(busy)}
          close={() => setAccessAction(null)}
          submit={async (operation) => {
            if (await runOperation(`access:${accessAction.kind}`, operation, "访问治理操作失败")) {
              setAccessAction(null);
            }
          }}
        />
      ) : null}
      {apiKeyAction ? (
        <ApiKeyActionModal
          action={apiKeyAction}
          catalog={workspace.apiKeyCatalog}
          busy={Boolean(busy)}
          close={() => setApiKeyAction(null)}
          submit={async (operation) => {
            const result = await runApiKeyOperation(`api-key:${apiKeyAction.kind}`, operation, "API 密钥操作失败");
            if (result) {
              setApiKeyAction(null);
              if ("secret" in result) setApiKeySecret(result);
            }
          }}
        />
      ) : null}
      {apiKeySecret ? <ApiKeySecretModal item={apiKeySecret} close={() => setApiKeySecret(null)} /> : null}
      {llmAction ? (
        <LLMProviderModal
          action={llmAction}
          busy={Boolean(busy)}
          close={() => setLlmAction(null)}
          submit={async (operation) => {
            if (await runLlmOperation(`llm:${llmAction.kind}`, operation, "模型设置保存失败")) {
              setLlmAction(null);
            }
          }}
        />
      ) : null}
    </section>
  );
}

function AccessPanel({
  workspace,
  onAction,
  onApiKeyAction,
  busy,
}: {
  workspace: Awaited<ReturnType<typeof loadEnterpriseWorkspace>>;
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
        <div className="table-frame enterprise-table">
          <table>
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
        </div>
      </section>

      <section aria-labelledby="enterprise-sessions-title">
        <header>
          <div>
            <h2 id="enterprise-sessions-title">登录会话</h2>
            <p>可单独撤销远程会话；角色或账户状态变化会使该用户全部会话失效。</p>
          </div>
        </header>
        <div className="table-frame enterprise-table">
          <table>
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
        </div>
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
        <div className="table-frame enterprise-table">
          <table>
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
        </div>
      </section>

      <section aria-labelledby="enterprise-clients-title">
        <header>
          <div>
            <h2 id="enterprise-clients-title">API / MCP Clients</h2>
            <p>远程 Agent 身份与主体绑定状态。</p>
          </div>
        </header>
        <div className="table-frame enterprise-table">
          <table>
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
        </div>
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

function queueCount(value: unknown, key: string): number {
  if (!value || typeof value !== "object") return 0;
  const count = (value as Record<string, unknown>)[key];
  return typeof count === "number" ? count : 0;
}

function deliveryDeadCount(value: unknown): number {
  if (!value || typeof value !== "object") return 0;
  return Object.values(value as Record<string, unknown>).reduce<number>(
    (total, states) => total + queueCount(states, "dead"),
    0,
  );
}

function PlatformOperationsPanel({ workspace }: { workspace: Awaited<ReturnType<typeof loadEnterpriseWorkspace>> }) {
  const platform = workspace.platform;
  const ingestion = platform.queues.ingestion;
  const outbox = platform.queues.outbox;
  const governance = platform.queues.governance;
  const deliveries = platform.queues.deliveries;
  const queueMetrics = [
    ["待运行入库", queueCount(ingestion, "pending")],
    ["运行中入库", queueCount(ingestion, "running")],
    ["过期心跳", queueCount(ingestion, "stale")],
    ["待发布事件", queueCount(outbox, "pending")],
    ["失败事件", queueCount(outbox, "failed")],
    ["投影死信", deliveryDeadCount(deliveries)],
    ["待审核事实", queueCount(governance, "review_pending")],
  ] as const;

  return (
    <div className="platform-operations">
      <section aria-labelledby="platform-services-title">
        <header>
          <div>
            <h2 id="platform-services-title">服务与责任边界</h2>
            <p>应用内信号与外部部署探针分开呈现；没有生产遥测时不会显示为已达标。</p>
          </div>
          <span className="cell-subtitle">快照 {formatDate(platform.generated_at, true)}</span>
        </header>
        <div className="table-frame enterprise-table">
          <table aria-label="平台服务状态">
            <thead>
              <tr>
                <th>服务</th>
                <th>负责人</th>
                <th>状态</th>
                <th>判定依据</th>
              </tr>
            </thead>
            <tbody>
              {platform.services.map((service) => (
                <tr key={service.service_id}>
                  <td className="mono-value">{service.service_id}</td>
                  <td>{service.owner}</td>
                  <td>
                    <StatusBadge value={service.status} />
                  </td>
                  <td>{service.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="platform-queues-title">
        <header>
          <div>
            <h2 id="platform-queues-title">队列、工作流与模型预算</h2>
            <p>计数直接来自当前租户权威库；模型统计仅汇总远程 API 运行记录。</p>
          </div>
        </header>
        <dl className="platform-queue-metrics">
          {queueMetrics.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="platform-runtime-grid">
          <dl>
            <div>
              <dt>工作流引擎</dt>
              <dd>{platform.workflow.engine.toUpperCase()}</dd>
            </div>
            <div>
              <dt>任务队列</dt>
              <dd className="mono-value">{platform.workflow.task_queue}</dd>
            </div>
            <div>
              <dt>最大并发活动</dt>
              <dd>{platform.workflow.max_concurrent_activities}</dd>
            </div>
          </dl>
          <dl>
            <div>
              <dt>24h 模型运行</dt>
              <dd>{platform.model_budget.run_count}</dd>
            </div>
            <div>
              <dt>输入 / 输出 token</dt>
              <dd>
                {platform.model_budget.input_tokens} / {platform.model_budget.output_tokens}
              </dd>
            </div>
            <div>
              <dt>估算成本 / 单文档上限</dt>
              <dd>
                {platform.model_budget.estimated_cost} / {platform.model_budget.max_document_cost}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section aria-labelledby="platform-slo-title">
        <header>
          <div>
            <h2 id="platform-slo-title">SLO 与告警契约</h2>
            <p>目标来自版本化运维契约；达标结论必须由目标环境集中遥测证据给出。</p>
          </div>
        </header>
        <div className="table-frame enterprise-table">
          <table aria-label="平台 SLO">
            <thead>
              <tr>
                <th>SLO</th>
                <th>服务</th>
                <th>指标</th>
                <th>目标 / 窗口</th>
                <th>评估</th>
              </tr>
            </thead>
            <tbody>
              {platform.slos.map((slo) => (
                <tr key={slo.id}>
                  <td>{slo.id}</td>
                  <td className="mono-value">{slo.service}</td>
                  <td>
                    {slo.metric}
                    <span className="cell-subtitle">{slo.measurement}</span>
                  </td>
                  <td>
                    {slo.target} / {slo.window}
                  </td>
                  <td>
                    <StatusBadge value="external" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="platform-evidence-title">
        <header>
          <div>
            <h2 id="platform-evidence-title">迁移、备份恢复与发布证据</h2>
            <p>只接受预定义位置的机器报告；缺失、损坏或未挂载都会显式阻断发布结论。</p>
          </div>
        </header>
        <div className="platform-migration">
          <span>数据库迁移</span>
          <StatusBadge value={platform.migration.status} />
          <code>{platform.migration.current_revision ?? "unknown"}</code>
          <span className="cell-subtitle">目标 {platform.migration.expected_revision ?? "unknown"}</span>
        </div>
        <div className="table-frame enterprise-table">
          <table aria-label="平台发布证据">
            <thead>
              <tr>
                <th>证据类别</th>
                <th>状态</th>
                <th>制品</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              {platform.evidence.map((evidence) => (
                <tr key={evidence.category}>
                  <td>{evidence.category}</td>
                  <td>
                    <StatusBadge value={evidence.status} />
                  </td>
                  <td className="mono-value">{evidence.artifact}</td>
                  <td>
                    {evidence.detail}
                    {evidence.sha256 ? (
                      <span className="cell-subtitle">sha256 {evidence.sha256.slice(0, 12)}</span>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="platform-events-title">
        <header>
          <div>
            <h2 id="platform-events-title">最近平台审计事件</h2>
            <p>保留请求关联 ID，便于从人员操作追踪到服务端日志和发布证据。</p>
          </div>
        </header>
        {platform.recent_events.length ? (
          <div className="table-frame enterprise-table">
            <table aria-label="最近平台审计事件">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作</th>
                  <th>资源</th>
                  <th>结果</th>
                  <th>请求 ID</th>
                </tr>
              </thead>
              <tbody>
                {platform.recent_events.map((event) => (
                  <tr key={event.id}>
                    <td>{formatDate(event.occurred_at, true)}</td>
                    <td>{event.action}</td>
                    <td>{event.resource_type}</td>
                    <td>
                      <StatusBadge value={event.outcome} />
                    </td>
                    <td className="mono-value">{event.request_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="暂无审计事件" detail="当前租户还没有可显示的平台操作记录。" />
        )}
      </section>
    </div>
  );
}

function EnterpriseOverview({ workspace }: { workspace: Awaited<ReturnType<typeof loadEnterpriseWorkspace>> }) {
  const overview = workspace.overview;
  const metrics = [
    ["用户总数", overview.user_count],
    ["活跃用户", overview.active_user_count],
    ["管理员", overview.admin_count],
    ["活跃用户组", overview.active_group_count],
    ["业务数据集", overview.dataset_count],
    ["活跃数据源", overview.active_source_count],
    ["24 小时审计事件", overview.audit_event_count_24h],
  ] as const;
  return (
    <>
      <section className="enterprise-metrics" aria-label="租户运营指标">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <strong>{value}</strong>
            <small>{label}</small>
          </div>
        ))}
      </section>
      <dl className="enterprise-tenant-details">
        <div>
          <dt>租户标识</dt>
          <dd>{overview.tenant.slug}</dd>
        </div>
        <div>
          <dt>运行状态</dt>
          <dd>
            <StatusBadge value={overview.tenant.active ? "active" : "disabled"} />
          </dd>
        </div>
        <div>
          <dt>创建时间</dt>
          <dd>{formatDate(overview.tenant.created_at, true)}</dd>
        </div>
        <div>
          <dt>租户 ID</dt>
          <dd className="mono-value">{overview.tenant.id}</dd>
        </div>
      </dl>
    </>
  );
}

function UsersPanel({
  users,
  currentUserId,
  busy,
  onCreate,
  onAction,
}: {
  users: EnterpriseUser[];
  currentUserId: string;
  busy: string;
  onCreate: () => void;
  onAction: (action: UserAction) => void;
}) {
  return (
    <>
      <div className="section-toolbar">
        <span>{users.length} 个企业账户</span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          新建用户
        </button>
      </div>
      <div className="table-frame enterprise-table">
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>角色</th>
              <th>状态</th>
              <th>身份源</th>
              <th>最近登录</th>
              <th aria-label="操作" />
            </tr>
          </thead>
          <tbody>
            {users.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.display_name}</strong>
                  <span className="cell-subtitle">{item.email}</span>
                </td>
                <td>{roleLabels[item.role]}</td>
                <td>
                  <StatusBadge value={item.active ? "active" : "disabled"} />
                </td>
                <td>{item.oidc_issuer ? "OIDC" : "本地账户"}</td>
                <td>{formatDate(item.last_login_at, true)}</td>
                <td>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      type="button"
                      title="调整角色"
                      aria-label={`调整 ${item.display_name} 的角色`}
                      onClick={() => onAction({ user: item, kind: "role" })}
                      disabled={item.id === currentUserId || Boolean(busy)}
                    >
                      <UserRoundCog size={16} />
                    </button>
                    <button
                      className="icon-button"
                      type="button"
                      title={item.active ? "停用账户" : "启用账户"}
                      aria-label={`${item.active ? "停用" : "启用"} ${item.display_name}`}
                      onClick={() => onAction({ user: item, kind: "status" })}
                      disabled={item.id === currentUserId || Boolean(busy)}
                    >
                      <KeyRound size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function GroupsPanel({
  groups,
  busy,
  onCreate,
  onAction,
}: {
  groups: EnterpriseGroup[];
  busy: string;
  onCreate: () => void;
  onAction: (action: GroupAction) => void;
}) {
  return (
    <>
      <div className="section-toolbar">
        <span>{groups.length} 个用户组</span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          新建用户组
        </button>
      </div>
      {groups.length ? (
        <div className="table-frame enterprise-table">
          <table>
            <thead>
              <tr>
                <th>用户组</th>
                <th>成员</th>
                <th>状态</th>
                <th>版本</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id}>
                  <td>
                    <strong>{group.name}</strong>
                    <span className="cell-subtitle">{group.description || "未填写说明"}</span>
                  </td>
                  <td>{group.member_count}</td>
                  <td>
                    <StatusBadge value={group.active ? "active" : "disabled"} />
                  </td>
                  <td>v{group.version}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title="编辑用户组"
                        aria-label={`编辑 ${group.name}`}
                        onClick={() => onAction({ group, kind: "edit" })}
                        disabled={Boolean(busy)}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        className="icon-button"
                        type="button"
                        title="管理成员"
                        aria-label={`管理 ${group.name} 的成员`}
                        onClick={() => onAction({ group, kind: "members" })}
                        disabled={Boolean(busy)}
                      >
                        <UsersRound size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="尚未建立用户组" detail="用户组用于集中维护组织成员，后续可绑定细粒度资源策略。" />
      )}
    </>
  );
}

function LLMProvidersPanel({
  providers,
  busy,
  onCreate,
  onEdit,
  onPrimary,
  onTest,
}: {
  providers: EnterpriseLLMProvider[];
  busy: string;
  onCreate: () => void;
  onEdit: (provider: EnterpriseLLMProvider) => void;
  onPrimary: (provider: EnterpriseLLMProvider) => void;
  onTest: (provider: EnterpriseLLMProvider) => void;
}) {
  const activeProviders = providers.filter((provider) => provider.active).sort((a, b) => a.priority - b.priority);
  const primaryProvider = activeProviders.find((provider) => provider.priority === 0) ?? activeProviders[0];
  const fallbackProviders = primaryProvider
    ? activeProviders.filter((provider) => provider.id !== primaryProvider.id)
    : [];
  return (
    <div className="enterprise-llm-settings">
      <div className="section-toolbar">
        <span>
          <BrainCircuit size={16} /> {providers.length} 个远程模型供应商 · 按顺序自动故障转移
        </span>
        <button className="primary-button" type="button" onClick={onCreate} disabled={Boolean(busy)}>
          <Plus size={16} />
          增加 LLM
        </button>
      </div>
      <fieldset className="enterprise-modal-subject" aria-label={"\u5f53\u524d LLM \u8c03\u7528\u987a\u5e8f"}>
        <legend>{"\u5f53\u524d\u8c03\u7528\u987a\u5e8f"}</legend>
        {primaryProvider ? (
          <span>
            {"\u4e3b\u6a21\u578b\uff1a"}
            {primaryProvider.model}
            {fallbackProviders.length
              ? ` \u2192 \u5907\u7528\uff1a${fallbackProviders.map((provider) => provider.model).join(" \u2192 ")}`
              : " \u00b7 \u5c1a\u672a\u914d\u7f6e\u5907\u7528\u6a21\u578b"}
          </span>
        ) : (
          <span>
            {
              "\u5c1a\u672a\u542f\u7528\u6a21\u578b\u3002\u8bf7\u5148\u589e\u52a0 MiMo v2.5\uff0c\u518d\u589e\u52a0 GLM 5.2 \u4f5c\u4e3a\u5907\u7528\u3002"
            }
          </span>
        )}
        <span>{`\u4e3b\u6a21\u578b\u53d1\u751f\u8d85\u65f6\u3001 408\u3001 429\u3001 5xx \u6216\u7f51\u7edc\u6545\u969c\u65f6\uff0c\u7cfb\u7edf\u4f1a\u6309\u987a\u5e8f\u4f7f\u7528\u540e\u7eed\u6a21\u578b\u3002`}</span>
      </fieldset>
      {providers.length ? (
        <div className="table-frame enterprise-table">
          <table aria-label="LLM 供应商顺序">
            <thead>
              <tr>
                <th>顺序</th>
                <th>供应商与模型</th>
                <th>协议</th>
                <th>超时策略</th>
                <th>连接状态</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => (
                <tr key={provider.id}>
                  <td>
                    {provider.priority === 0 && provider.active ? (
                      <span className="llm-primary-label">
                        <Star size={14} /> 主模型
                      </span>
                    ) : (
                      `备用 ${provider.priority}`
                    )}
                  </td>
                  <td>
                    <strong>{provider.name}</strong>
                    <span className="cell-subtitle">
                      {provider.model} · Key {provider.api_key_fingerprint}
                    </span>
                    <span className="cell-subtitle mono-value">{provider.base_url}</span>
                  </td>
                  <td>
                    {provider.response_format_mode}
                    <span className="cell-subtitle">思考模式：{provider.thinking_mode}</span>
                  </td>
                  <td>
                    {provider.request_timeout_seconds}s × {provider.request_attempts}
                    <span className="cell-subtitle">
                      最大输出 {provider.max_output_tokens_per_segment.toLocaleString()} tokens
                    </span>
                  </td>
                  <td>
                    <StatusBadge value={provider.active ? "active" : "disabled"} />
                    <span className="cell-subtitle">
                      {provider.last_test_status
                        ? `${provider.last_test_status === "passed" ? "测试通过" : "测试失败"} · ${formatDate(provider.last_tested_at, true)}`
                        : "尚未测试"}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title="测试连接"
                        aria-label={`测试 ${provider.name} 连接`}
                        onClick={() => onTest(provider)}
                        disabled={Boolean(busy) || !provider.active}
                      >
                        <TestTube2 size={16} />
                      </button>
                      {provider.priority !== 0 ? (
                        <button
                          className="icon-button"
                          type="button"
                          title="设为主模型"
                          aria-label={`将 ${provider.name} 设为主模型`}
                          onClick={() => onPrimary(provider)}
                          disabled={Boolean(busy) || !provider.active}
                        >
                          <Star size={16} />
                        </button>
                      ) : null}
                      <button
                        className="icon-button"
                        type="button"
                        title="编辑模型设置"
                        aria-label={`编辑 ${provider.name}`}
                        onClick={() => onEdit(provider)}
                        disabled={Boolean(busy)}
                      >
                        <Pencil size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="尚未配置远程模型"
          detail="增加经过批准的 OpenAI-compatible HTTPS 模型；保存后，新治理任务会按这里的顺序调用。"
        />
      )}
    </div>
  );
}

function AuditPanel({
  filters,
  draftAction,
  setDraftAction,
  setFilters,
  page,
  loading,
}: {
  filters: EnterpriseAuditFilters;
  draftAction: string;
  setDraftAction: (value: string) => void;
  setFilters: (value: EnterpriseAuditFilters) => void;
  page: Awaited<ReturnType<typeof loadEnterpriseAudit>> | undefined;
  loading: boolean;
}) {
  return (
    <>
      <form
        className="enterprise-audit-filter"
        onSubmit={(event) => {
          event.preventDefault();
          setFilters({ ...filters, cursor: undefined, action: draftAction.trim() || undefined });
        }}
      >
        <input
          value={draftAction}
          onChange={(event) => setDraftAction(event.target.value)}
          placeholder="按动作筛选，例如 enterprise.user.created"
          aria-label="审计动作"
        />
        <select
          value={filters.actorType ?? ""}
          onChange={(event) =>
            setFilters({
              ...filters,
              cursor: undefined,
              actorType: (event.target.value || undefined) as EnterpriseAuditFilters["actorType"],
            })
          }
          aria-label="操作者类型"
        >
          <option value="">全部操作者</option>
          <option value="user">用户</option>
          <option value="api_key">API Key</option>
          <option value="agent">Agent</option>
        </select>
        <select
          value={filters.outcome ?? ""}
          onChange={(event) => setFilters({ ...filters, cursor: undefined, outcome: event.target.value || undefined })}
          aria-label="执行结果"
        >
          <option value="">全部结果</option>
          <option value="success">成功</option>
          <option value="denied">拒绝</option>
          <option value="failed">失败</option>
        </select>
        <button className="secondary-button" type="submit" disabled={loading}>
          筛选
        </button>
      </form>
      {loading && !page ? <Spinner label="正在读取审计日志" /> : null}
      {page?.items.length ? (
        <div className="table-frame enterprise-table">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>动作</th>
                <th>操作者</th>
                <th>资源</th>
                <th>结果</th>
                <th>请求 ID</th>
              </tr>
            </thead>
            <tbody>
              {page.items.map((event) => (
                <tr key={event.id}>
                  <td>{formatDate(event.occurred_at, true)}</td>
                  <td className="mono-value">{event.action}</td>
                  <td>
                    <strong>{event.actor_type}</strong>
                    <span className="cell-subtitle">{event.actor_id}</span>
                  </td>
                  <td>
                    {event.resource_type}
                    <span className="cell-subtitle">{event.resource_id ?? "--"}</span>
                  </td>
                  <td>
                    <StatusBadge value={event.outcome} />
                  </td>
                  <td className="mono-value">{event.request_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : page ? (
        <EmptyState title="没有符合条件的审计事件" />
      ) : null}
      <div className="enterprise-audit-pagination">
        {filters.cursor ? (
          <button className="text-button" type="button" onClick={() => setFilters({ ...filters, cursor: undefined })}>
            返回第一页
          </button>
        ) : null}
        {page?.next_cursor ? (
          <button
            className="secondary-button"
            type="button"
            onClick={() => setFilters({ ...filters, cursor: page.next_cursor ?? undefined })}
            disabled={loading}
          >
            下一页
          </button>
        ) : null}
      </div>
    </>
  );
}

function ModalShell({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(
    document.activeElement instanceof HTMLElement ? document.activeElement : null,
  );

  useEffect(() => {
    queueMicrotask(() => {
      if (!dialogRef.current?.contains(document.activeElement)) {
        closeButtonRef.current?.focus();
      }
    });

    return () => {
      const previousActiveElement = previousActiveElementRef.current;
      if (previousActiveElement?.isConnected) {
        previousActiveElement.focus();
      }
    };
  }, []);

  return (
    <div className="modal-backdrop" role="presentation">
      <div ref={dialogRef} className="modal-panel" role="dialog" aria-modal="true" aria-label={title}>
        <header>
          <h2>{title}</h2>
          <button
            ref={closeButtonRef}
            className="icon-button"
            type="button"
            onClick={close}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

function LLMProviderModal({
  action,
  busy,
  close,
  submit,
}: {
  action: LLMAction;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseLLMProviderOperation) => Promise<void>;
}) {
  const provider = action.kind === "create" ? null : action.provider;
  const [name, setName] = useState(provider?.name ?? "");
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? "");
  const [model, setModel] = useState(provider?.model ?? "");
  const [apiKey, setApiKey] = useState("");
  const [active, setActive] = useState(provider?.active ?? true);
  const [responseMode, setResponseMode] = useState(provider?.response_format_mode ?? "prompt_only");
  const [thinkingMode, setThinkingMode] = useState(provider?.thinking_mode ?? "disabled");
  const [includeSchema, setIncludeSchema] = useState(provider?.include_schema_in_prompt ?? true);
  const [maxOutputTokens, setMaxOutputTokens] = useState(provider?.max_output_tokens_per_segment ?? 16_384);
  const [timeoutSeconds, setTimeoutSeconds] = useState(provider?.request_timeout_seconds ?? 120);
  const [attempts, setAttempts] = useState(provider?.request_attempts ?? 2);
  const [reason, setReason] = useState("");

  const applyPreset = (preset: LLMProviderPreset) => {
    const values = llmProviderPresets[preset];
    setName(values.name);
    setBaseUrl(values.baseUrl);
    setModel(values.model);
    setResponseMode("prompt_only");
    setThinkingMode("disabled");
    setIncludeSchema(true);
    setMaxOutputTokens(16_384);
    setTimeoutSeconds(120);
    setAttempts(values.attempts);
    setApiKey("");
  };

  if (action.kind === "primary") {
    return (
      <ModalShell title={`将 ${action.provider.name} 设为主模型`} close={close}>
        <form
          className="stacked-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit({
              kind: "make-llm-primary",
              providerId: action.provider.id,
              requestBody: { expected_version: action.provider.version, reason },
            });
          }}
        >
          <p>保存后，新启动的 AI 入库任务会先调用该模型；超时或可重试故障时再调用后续备用模型。</p>
          <label>
            调整原因
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} required />
          </label>
          <div className="modal-actions">
            <button className="secondary-button" type="button" onClick={close} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              {busy ? "切换中" : "确认切换"}
            </button>
          </div>
        </form>
      </ModalShell>
    );
  }

  return (
    <ModalShell title={action.kind === "create" ? "增加 LLM" : `编辑 ${action.provider.name}`} close={close}>
      <form
        className="stacked-form llm-provider-form"
        onSubmit={(event) => {
          event.preventDefault();
          const common = {
            name,
            base_url: baseUrl,
            model,
            response_format_mode: responseMode,
            thinking_mode: thinkingMode,
            include_schema_in_prompt: includeSchema,
            max_output_tokens_per_segment: maxOutputTokens,
            request_timeout_seconds: timeoutSeconds,
            request_attempts: attempts,
            reason,
          };
          const operation: EnterpriseLLMProviderOperation =
            action.kind === "create"
              ? { kind: "create-llm-provider", requestBody: { ...common, api_key: apiKey } }
              : {
                  kind: "update-llm-provider",
                  providerId: action.provider.id,
                  requestBody: {
                    ...common,
                    expected_version: action.provider.version,
                    api_key: apiKey || null,
                    active,
                  },
                };
          void submit(operation);
        }}
      >
        {action.kind === "create" ? (
          <fieldset className="enterprise-modal-subject" aria-label={"LLM \u63a8\u8350\u914d\u7f6e"}>
            <legend>{"\u5feb\u901f\u914d\u7f6e\u63a8\u8350\u6a21\u578b"}</legend>
            <span>
              {
                "\u5efa\u8bae\u5148\u4fdd\u5b58 MiMo v2.5 \u4f5c\u4e3a\u4e3b\u6a21\u578b\uff0c\u518d\u4fdd\u5b58 GLM 5.2 \u4f5c\u4e3a\u8d85\u65f6\u5907\u7528\u6a21\u578b\u3002"
              }
            </span>
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={() => applyPreset("mimo")} disabled={busy}>
                {"\u4f7f\u7528 MiMo v2.5 \u4e3b\u6a21\u578b\u9884\u8bbe"}
              </button>
              <button className="secondary-button" type="button" onClick={() => applyPreset("glm")} disabled={busy}>
                {"\u4f7f\u7528 GLM 5.2 \u5907\u7528\u9884\u8bbe"}
              </button>
            </div>
          </fieldset>
        ) : null}
        <div className="form-grid">
          <label>
            供应商名称
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required />
          </label>
          <label>
            模型 ID
            <input value={model} onChange={(event) => setModel(event.target.value)} maxLength={500} required />
          </label>
          <label className="full-span">
            API 根地址
            <input
              type="url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="https://provider.example/v1"
              required
            />
          </label>
          <label className="full-span">
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="new-password"
              placeholder={provider ? "留空则保持现有密钥" : "输入供应商 API Key"}
              required={!provider}
            />
          </label>
          <label>
            响应协议
            <select
              value={responseMode}
              onChange={(event) => setResponseMode(event.target.value as typeof responseMode)}
            >
              <option value="prompt_only">Prompt JSON Schema</option>
              <option value="json_object">JSON Object</option>
              <option value="json_schema">JSON Schema</option>
            </select>
          </label>
          <label>
            思考模式
            <select
              value={thinkingMode}
              onChange={(event) => setThinkingMode(event.target.value as typeof thinkingMode)}
            >
              <option value="disabled">关闭</option>
              <option value="provider_default">供应商默认</option>
              <option value="enabled">开启</option>
            </select>
          </label>
          <label>
            单次超时（秒）
            <input
              type="number"
              min={1}
              max={600}
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
              required
            />
          </label>
          <label>
            尝试次数
            <input
              type="number"
              min={1}
              max={8}
              value={attempts}
              onChange={(event) => setAttempts(Number(event.target.value))}
              required
            />
          </label>
          <label>
            最大输出 tokens
            <input
              type="number"
              min={256}
              max={131072}
              value={maxOutputTokens}
              onChange={(event) => setMaxOutputTokens(Number(event.target.value))}
              required
            />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={includeSchema}
              onChange={(event) => setIncludeSchema(event.target.checked)}
            />
            在提示词中附带 Schema
          </label>
          {provider ? (
            <label className="checkbox-field">
              <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
              启用此供应商
            </label>
          ) : null}
        </div>
        <label>
          变更原因
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            minLength={3}
            maxLength={500}
            required
          />
        </label>
        <div className="modal-actions">
          <button className="secondary-button" type="button" onClick={close} disabled={busy}>
            取消
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={
              busy ||
              !name.trim() ||
              !baseUrl.trim() ||
              !model.trim() ||
              (!provider && !apiKey) ||
              reason.trim().length < 3
            }
          >
            {busy ? "保存中" : "保存设置"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function CreateUserModal({
  authMode,
  busy,
  close,
  submit,
}: {
  authMode: AuthMode;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [password, setPassword] = useState("");
  const [issuer, setIssuer] = useState("");
  const [subject, setSubject] = useState("");
  return (
    <ModalShell title="新建企业用户" close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit({
            kind: "create-user",
            requestBody: {
              email: email.trim(),
              display_name: displayName.trim(),
              role,
              initial_password: authMode === "local" ? password : null,
              oidc_issuer: authMode === "oidc" ? issuer.trim() : null,
              oidc_subject: authMode === "oidc" ? subject.trim() : null,
            },
          });
        }}
      >
        <label>
          邮箱
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          显示名称
          <input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
        </label>
        <label>
          企业角色
          <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
            <option value="viewer">浏览者</option>
            <option value="analyst">分析师</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        {authMode === "local" ? (
          <label>
            初始密码
            <input
              type="password"
              minLength={12}
              maxLength={200}
              required
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
        ) : (
          <>
            <label>
              OIDC Issuer
              <input type="url" required value={issuer} onChange={(event) => setIssuer(event.target.value)} />
            </label>
            <label>
              OIDC Subject
              <input required value={subject} onChange={(event) => setSubject(event.target.value)} />
            </label>
          </>
        )}
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            <ShieldCheck size={16} />
            创建用户
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function UserActionModal({
  action,
  busy,
  close,
  submit,
}: {
  action: UserAction;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [role, setRole] = useState<UserRole>(action.user.role);
  const [reason, setReason] = useState("");
  const title = action.kind === "role" ? "调整用户角色" : action.user.active ? "停用企业用户" : "启用企业用户";
  return (
    <ModalShell title={title} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const operation: EnterpriseOperation =
            action.kind === "role"
              ? {
                  kind: "update-user-role",
                  userId: action.user.id,
                  requestBody: { expected_token_version: action.user.token_version, role, reason: reason.trim() },
                }
              : {
                  kind: "update-user-status",
                  userId: action.user.id,
                  requestBody: {
                    expected_token_version: action.user.token_version,
                    active: !action.user.active,
                    reason: reason.trim(),
                  },
                };
          void submit(operation);
        }}
      >
        <p className="enterprise-modal-subject">
          {action.user.display_name}
          <span>{action.user.email}</span>
        </p>
        {action.kind === "role" ? (
          <label>
            新角色
            <select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
              <option value="viewer">浏览者</option>
              <option value="analyst">分析师</option>
              <option value="admin">管理员</option>
            </select>
          </label>
        ) : null}
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
          <button
            className="primary-button"
            type="submit"
            disabled={busy || (action.kind === "role" && role === action.user.role)}
          >
            确认变更
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function AccessActionModal({
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

const apiKeyScopeLabels: Record<string, string> = {
  "mcp:connect": "MCP 连接",
  "entities:read": "实体检索",
  "dossiers:read": "专业档案",
  "targets:read": "靶点情报",
  "activities:read": "活性数据",
  "pipelines:read": "研发管线",
  "structures:read": "化学结构",
  "trials:read": "临床试验",
  "patents:read": "专利情报",
  "deals:read": "交易情报",
  "regulatory:read": "监管情报",
  "epidemiology:read": "流行病学",
  "news:read": "资讯事件",
  "knowledge:read": "知识页面",
  "evidence:read": "证据检索",
  "workspace:export": "受控导出",
};

function apiKeyScopeLabel(scope: string): string {
  return apiKeyScopeLabels[scope] ?? scope;
}

function localDateTimeValue(value?: string | null, daysFromNow = 90): string {
  const date = value ? new Date(value) : new Date(Date.now() + daysFromNow * 86_400_000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function ApiKeyActionModal({
  action,
  catalog,
  busy,
  close,
  submit,
}: {
  action: ApiKeyAction;
  catalog: EnterpriseApiKeyCatalog;
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseApiKeyOperation) => Promise<void>;
}) {
  const apiKey = action.kind === "create" ? null : action.apiKey;
  const [name, setName] = useState(apiKey?.name ?? "");
  const [expiresAt, setExpiresAt] = useState(localDateTimeValue(apiKey?.expires_at));
  const [scopes, setScopes] = useState<string[]>(
    action.kind === "create" ? [...catalog.allowed_scopes] : [...(apiKey?.scopes ?? [])],
  );
  const [reason, setReason] = useState("");
  const title =
    action.kind === "create" ? "新建 Agent API 密钥" : action.kind === "rotate" ? "轮换 API 密钥" : "撤销 API 密钥";
  const canSubmit =
    reason.trim().length >= 3 &&
    (action.kind === "revoke" || (name.trim().length > 0 && expiresAt.length > 0 && scopes.length >= 2));

  return (
    <ModalShell title={title} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (action.kind === "create") {
            void submit({
              kind: "create-api-key",
              requestBody: {
                name: name.trim(),
                scopes,
                expires_at: new Date(expiresAt).toISOString(),
                reason: reason.trim(),
              },
            });
          } else if (action.kind === "rotate") {
            void submit({
              kind: "rotate-api-key",
              keyId: action.apiKey.id,
              requestBody: {
                name: name.trim(),
                expires_at: new Date(expiresAt).toISOString(),
                reason: reason.trim(),
              },
            });
          } else {
            void submit({
              kind: "revoke-api-key",
              keyId: action.apiKey.id,
              requestBody: { reason: reason.trim() },
            });
          }
        }}
      >
        {apiKey ? (
          <p className="enterprise-modal-subject">
            {apiKey.name}
            <span className="mono-value">{apiKey.prefix}</span>
          </p>
        ) : null}
        {action.kind !== "revoke" ? (
          <>
            <label>
              密钥名称
              <input required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              到期时间
              <input
                required
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
              <span className="cell-subtitle">最长 {catalog.max_ttl_days} 天，到期后自动拒绝认证。</span>
            </label>
          </>
        ) : null}
        {action.kind === "create" ? (
          <fieldset className="enterprise-member-list">
            <legend>授权范围</legend>
            {catalog.allowed_scopes.map((scope) => (
              <label key={scope}>
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  disabled={scope === catalog.required_scope}
                  onChange={(event) =>
                    setScopes((current) =>
                      event.target.checked
                        ? [...new Set([...current, scope])]
                        : current.filter((item) => item !== scope),
                    )
                  }
                />
                <span>
                  {apiKeyScopeLabel(scope)}
                  <small className="mono-value">{scope}</small>
                </span>
              </label>
            ))}
          </fieldset>
        ) : null}
        {action.kind === "revoke" ? (
          <p className="inline-warning">撤销后不能重新启用；该密钥及其 API-key 商业主体会立即失效。</p>
        ) : null}
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
          <button className="primary-button" type="submit" disabled={busy || !canSubmit}>
            {action.kind === "create" ? "创建密钥" : action.kind === "rotate" ? "轮换密钥" : "确认撤销"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function ApiKeySecretModal({ item, close }: { item: EnterpriseApiKeySecret; close: () => void }) {
  const [copyStatus, setCopyStatus] = useState("");
  const secretInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    secretInputRef.current?.focus();
    secretInputRef.current?.select();
  }, []);

  return (
    <ModalShell title="立即保存 API 密钥" close={close}>
      <p className="inline-warning" role="status">
        这是完整密钥唯一一次显示。关闭后平台无法找回，请立即存入获批的密钥管理器。
      </p>
      <label>
        API 密钥
        <input ref={secretInputRef} className="mono-value" aria-label="API 密钥" readOnly value={item.secret} />
      </label>
      <p className="enterprise-modal-subject">
        {item.name}
        <span className="mono-value">密钥 ID：{item.id}</span>
      </p>
      {copyStatus ? <p role="status">{copyStatus}</p> : null}
      <div className="form-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            if (!navigator.clipboard) {
              setCopyStatus("当前浏览器不允许自动复制，请手动选择密钥。");
              return;
            }
            void navigator.clipboard.writeText(item.secret).then(
              () => setCopyStatus("已复制"),
              () => setCopyStatus("复制失败，请手动选择密钥。"),
            );
          }}
        >
          <Copy size={16} />
          复制密钥
        </button>
        <button className="primary-button" type="button" onClick={close}>
          已安全保存
        </button>
      </div>
    </ModalShell>
  );
}

function CreateGroupModal({
  busy,
  close,
  submit,
}: {
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return (
    <ModalShell title="新建用户组" close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit({ kind: "create-group", requestBody: { name: name.trim(), description: description.trim() } });
        }}
      >
        <label>
          用户组名称
          <input required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          说明
          <textarea maxLength={500} value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <div className="form-actions">
          <button className="secondary-button" type="button" onClick={close}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={busy}>
            创建用户组
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function GroupActionModal({
  action,
  users,
  busy,
  close,
  submit,
}: {
  action: GroupAction;
  users: EnterpriseUser[];
  busy: boolean;
  close: () => void;
  submit: (operation: EnterpriseOperation) => Promise<void>;
}) {
  const [name, setName] = useState(action.group.name);
  const [description, setDescription] = useState(action.group.description);
  const [active, setActive] = useState(action.group.active);
  const [memberIds, setMemberIds] = useState<string[]>(action.group.member_ids);
  const [reason, setReason] = useState("");
  return (
    <ModalShell title={action.kind === "edit" ? "编辑用户组" : "管理用户组成员"} close={close}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit(
            action.kind === "edit"
              ? {
                  kind: "update-group",
                  groupId: action.group.id,
                  requestBody: {
                    expected_version: action.group.version,
                    name: name.trim(),
                    description: description.trim(),
                    active,
                    reason: reason.trim(),
                  },
                }
              : {
                  kind: "update-group-members",
                  groupId: action.group.id,
                  requestBody: {
                    expected_version: action.group.version,
                    user_ids: memberIds,
                    reason: reason.trim(),
                  },
                },
          );
        }}
      >
        {action.kind === "edit" ? (
          <>
            <label>
              用户组名称
              <input required maxLength={160} value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              说明
              <textarea maxLength={500} value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            <label className="check-control">
              <input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />
              启用用户组
            </label>
          </>
        ) : (
          <fieldset className="enterprise-member-list">
            <legend>{action.group.name}</legend>
            {users
              .filter((item) => item.active)
              .map((item) => (
                <label className="check-control" key={item.id}>
                  <input
                    type="checkbox"
                    checked={memberIds.includes(item.id)}
                    onChange={(event) =>
                      setMemberIds((current) =>
                        event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id),
                      )
                    }
                  />
                  <span>
                    {item.display_name} <small>{item.email}</small>
                  </span>
                </label>
              ))}
          </fieldset>
        )}
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
          <button className="primary-button" type="submit" disabled={busy}>
            保存变更
          </button>
        </div>
      </form>
    </ModalShell>
  );
}
