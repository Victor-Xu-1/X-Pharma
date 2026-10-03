import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { accountInvitations } from "../lib/contracts/accounts";
import {
  executeEnterpriseApiKeyOperation,
  executeEnterpriseLLMProviderOperation,
  executeEnterpriseOperation,
  loadEnterpriseAccess,
  loadEnterpriseAudit,
  loadEnterpriseGroups,
  loadEnterpriseModels,
  loadEnterpriseOverview,
  loadEnterprisePlatform,
  loadEnterpriseUsers,
} from "../lib/contracts/enterprise";
import type { User } from "../lib/types";
import { EnterpriseView } from "../views/EnterpriseView";
import { PlatformOperationsPanel } from "../views/environment/PlatformPanel";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/enterprise", () => ({
  enterpriseKeys: {
    root: ["enterprise"],
    overview: ["enterprise", "overview"],
    users: ["enterprise", "users"],
    groups: ["enterprise", "groups"],
    access: ["enterprise", "access"],
    models: ["enterprise", "models"],
    platform: ["enterprise", "platform"],
    audit: (filters: unknown) => ["enterprise", "audit", filters],
  },
  executeEnterpriseApiKeyOperation: vi.fn(),
  executeEnterpriseLLMProviderOperation: vi.fn(),
  executeEnterpriseOperation: vi.fn(),
  loadEnterpriseAudit: vi.fn(),
  loadEnterpriseAccess: vi.fn(),
  loadEnterpriseGroups: vi.fn(),
  loadEnterpriseModels: vi.fn(),
  loadEnterpriseOverview: vi.fn(),
  loadEnterprisePlatform: vi.fn(),
  loadEnterpriseUsers: vi.fn(),
}));
vi.mock("../lib/contracts/accounts", () => ({
  accountInvitations: vi.fn(),
  issueAccountInvitation: vi.fn(),
  revokeAccountInvitation: vi.fn(),
}));

it("keeps registration invitations usable when unrelated platform data is unavailable", async () => {
  vi.mocked(loadEnterpriseOverview).mockRejectedValue(new Error("Organization overview is unavailable"));
  vi.mocked(accountInvitations).mockResolvedValue([]);
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await screen.findByRole("tab", { name: "注册邀请" });
  fireEvent.click(screen.getByRole("tab", { name: "注册邀请" }));
  await screen.findByText("暂无注册邀请");
  expect(accountInvitations).toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "生成注册邀请码" })).toBeDisabled();
});

it("keeps user management usable when platform operations are unavailable", async () => {
  vi.mocked(loadEnterprisePlatform).mockRejectedValue(new Error("Platform status is unavailable"));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户与角色");
  await screen.findByText("Research Analyst");
  expect(screen.queryByRole("tab", { name: "平台运营" })).not.toBeInTheDocument();
  expect(loadEnterprisePlatform).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "新建用户" })).toBeEnabled();
});

async function selectEnterpriseTab(name: string) {
  fireEvent.click(await screen.findByRole("tab", { name }));
  await waitFor(() => expect(screen.queryByText("正在读取企业管理数据")).not.toBeInTheDocument());
}

const user: User = {
  id: "admin-1",
  tenant_id: "tenant-1",
  email: "admin@example.test",
  display_name: "Administrator",
  role: "admin",
};

const workspace = {
  overview: {
    tenant: {
      id: "tenant-1",
      slug: "pharma-rd",
      name: "Pharma R&D",
      active: true,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
    user_count: 2,
    active_user_count: 2,
    admin_count: 1,
    group_count: 1,
    active_group_count: 1,
    dataset_count: 5,
    active_source_count: 3,
    audit_event_count_24h: 12,
  },
  users: [
    {
      id: "admin-1",
      tenant_id: "tenant-1",
      email: "admin@example.test",
      display_name: "Administrator",
      role: "admin" as const,
      active: true,
      token_version: 1,
      last_login_at: "2026-07-19T01:00:00Z",
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
    {
      id: "analyst-1",
      tenant_id: "tenant-1",
      email: "analyst@example.test",
      display_name: "Research Analyst",
      role: "analyst" as const,
      active: true,
      token_version: 2,
      last_login_at: null,
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
  ],
  groups: [
    {
      id: "group-1",
      tenant_id: "tenant-1",
      name: "Research Operations",
      description: "Research team",
      active: true,
      version: 1,
      member_ids: ["analyst-1"],
      member_count: 1,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
  ],
  datasets: [
    {
      id: "dataset-1",
      dataset_key: "literature",
      display_name: "文献库",
      active: true,
      version: 1,
      required_scopes: ["evidence:read"],
      license_id: "tenant-owned-internal",
      license_policy_version: "tenant-owned-v1",
      permitted_channels: ["web" as const, "mcp" as const],
      license_current: true,
      attribution: "Tenant-provided source material",
    },
  ],
  sessions: [
    {
      id: "session-current",
      user_id: "admin-1",
      user_display_name: "Administrator",
      user_email: "admin@example.test",
      issued_at: "2026-07-19T01:00:00Z",
      expires_at: "2099-07-19T09:00:00Z",
      revoked_at: null,
      revoked_by_user_id: null,
      revoke_reason: null,
      current: true,
    },
    {
      id: "session-remote",
      user_id: "analyst-1",
      user_display_name: "Research Analyst",
      user_email: "analyst@example.test",
      issued_at: "2026-07-19T00:00:00Z",
      expires_at: "2099-07-19T08:00:00Z",
      revoked_at: null,
      revoked_by_user_id: null,
      revoke_reason: null,
      current: false,
    },
  ],
  apiKeyCatalog: {
    required_scope: "mcp:connect",
    allowed_scopes: ["mcp:connect", "entities:read", "targets:read"],
    min_ttl_hours: 1,
    max_ttl_days: 366,
    items: [
      {
        id: "key-1",
        name: "Research Agent Key",
        prefix: "phk_example1",
        scopes: ["mcp:connect", "entities:read", "targets:read"],
        active: true,
        status: "active" as const,
        last_used_at: null,
        expires_at: "2099-10-01T00:00:00Z",
        revoked_at: null,
        commercial_client_id: "client-1",
        commercial_client_name: "Research Agent",
        created_at: "2026-07-01T00:00:00Z",
        updated_at: "2026-07-01T00:00:00Z",
      },
    ],
  },
  clients: [
    {
      id: "client-1",
      client_key: "research-agent",
      display_name: "Research Agent",
      active: true,
      subjects: [],
      billing_account_key: "enterprise",
      subscription_key: "enterprise-plan",
      subscription_status: "active",
      available_units: "1000",
      active_reservations: 0,
      denial_count_24h: 0,
      last_policy_event_at: null,
      created_at: "2026-07-01T00:00:00Z",
    },
  ],
  retentionPolicies: [],
  legalHolds: [],
  platform: {
    generated_at: "2026-07-25T12:00:00Z",
    environment: "test",
    services: [
      {
        service_id: "api",
        owner: "platform-operations",
        escalation_policy: "role://platform-operations/on-call",
        status: "ready" as const,
        enabled: true,
        liveness: "observed" as const,
        queue_status: "not_applicable" as const,
        detail: "Current authenticated API request completed",
      },
      {
        service_id: "mcp",
        owner: "platform-operations",
        escalation_policy: "role://platform-operations/on-call",
        status: "external" as const,
        enabled: null,
        liveness: "unverified" as const,
        queue_status: "not_applicable" as const,
        detail: "MCP liveness is evaluated at the dedicated Agent entry",
      },
    ],
    queues: {
      ingestion: { pending: 2, running: 1, stale: 0 },
      outbox: { pending: 3, failed: 0 },
      deliveries: { opensearch: { retry: 1, dead: 0 } },
      governance: { review_pending: 4 },
    },
    workflow: {
      engine: "temporal" as const,
      enabled: true,
      namespace: "default",
      task_queue: "pharma-data-factory",
      max_concurrent_activities: 20,
    },
    model_budget: {
      window: "24h" as const,
      run_count: 12,
      input_tokens: 2400,
      output_tokens: 800,
      estimated_cost: "0.210000",
      failed_runs: 1,
      max_document_cost: "2.000000",
      provider: "remote_api",
      model: "mimo-v2.5",
    },
    slos: [
      {
        id: "web-availability",
        service: "api",
        metric: "http.server.duration",
        measurement: "success_ratio",
        target: 0.999,
        window: "30d",
        evaluation_status: "external_evidence_required" as const,
        error_budget_policy: "freeze_noncritical_changes",
      },
    ],
    alerts: [],
    migration: {
      current_revision: "fc5e8a1b3d72",
      expected_revision: "fc5e8a1b3d72",
      status: "current" as const,
    },
    evidence: [
      {
        category: "backup_restore" as const,
        status: "passed" as const,
        artifact: "backup_restore/report.json",
        sha256: "a".repeat(64),
        observed_at: "2026-07-25T11:00:00Z",
        detail: "Machine report status: passed",
      },
      {
        category: "release_candidate" as const,
        status: "missing" as const,
        artifact: "candidate-summary.json",
        sha256: null,
        observed_at: null,
        detail: "No machine-generated evidence is mounted",
      },
      {
        category: "production_topology" as const,
        status: "not_configured" as const,
        artifact: "production_topology/report.json",
        sha256: null,
        observed_at: null,
        detail: "Evidence mount is not configured for this environment",
      },
    ],
    recent_events: [],
  },
  llmProviders: [
    {
      id: "provider-mimo",
      name: "mimo",
      base_url: "https://token-plan-cn.xiaomimimo.com/v1",
      model: "mimo-v2.5",
      priority: 0,
      version: 2,
      active: true,
      api_key_configured: true,
      api_key_fingerprint: "abc123def4567890",
      response_format_mode: "prompt_only" as const,
      thinking_mode: "disabled" as const,
      include_schema_in_prompt: true,
      max_output_tokens_per_segment: 16384,
      request_timeout_seconds: 120,
      request_attempts: 2,
      last_tested_at: "2026-08-11T03:00:00Z",
      last_test_status: "passed" as const,
      last_test_message: "mimo-v2.5 · stop · request_id=yes",
      created_at: "2026-08-11T02:00:00Z",
      updated_at: "2026-08-11T03:00:00Z",
    },
    {
      id: "provider-glm",
      name: "glm",
      base_url: "https://chatapi.weixin.qq.com/openai/v1",
      model: "GLM-5.2",
      priority: 1,
      version: 1,
      active: true,
      api_key_configured: true,
      api_key_fingerprint: "def456abc1237890",
      response_format_mode: "prompt_only" as const,
      thinking_mode: "disabled" as const,
      include_schema_in_prompt: true,
      max_output_tokens_per_segment: 16384,
      request_timeout_seconds: 120,
      request_attempts: 1,
      last_tested_at: null,
      last_test_status: null,
      last_test_message: null,
      created_at: "2026-08-11T02:00:00Z",
      updated_at: "2026-08-11T02:00:00Z",
    },
  ],
};

beforeEach(() => {
  vi.mocked(loadEnterpriseOverview).mockResolvedValue(workspace.overview);
  vi.mocked(loadEnterpriseUsers).mockResolvedValue(workspace.users);
  vi.mocked(loadEnterpriseGroups).mockResolvedValue(workspace.groups);
  vi.mocked(loadEnterpriseAccess).mockResolvedValue(workspace);
  vi.mocked(loadEnterpriseModels).mockResolvedValue(workspace.llmProviders);
  vi.mocked(loadEnterprisePlatform).mockResolvedValue(workspace.platform);
  vi.mocked(loadEnterpriseAudit).mockResolvedValue({ items: [], next_cursor: null });
  vi.mocked(executeEnterpriseOperation).mockResolvedValue({});
  vi.mocked(executeEnterpriseApiKeyOperation).mockResolvedValue(workspace.apiKeyCatalog.items[0]);
  vi.mocked(executeEnterpriseLLMProviderOperation).mockResolvedValue(workspace.llmProviders[0]);
});

it("shows the primary and fallback LLM order and switches primary with an audited reason", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("模型设置");

  expect(screen.getByRole("table", { name: "LLM 供应商顺序" })).toHaveTextContent("mimo-v2.5");
  expect(screen.getByText("主模型")).toBeInTheDocument();
  expect(screen.getByText("备用 1")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "将 glm 设为主模型" }));
  fireEvent.change(screen.getByLabelText("调整原因"), { target: { value: "提升 GLM 为本次主模型" } });
  fireEvent.click(screen.getByRole("button", { name: "确认切换" }));

  await waitFor(() => expect(executeEnterpriseLLMProviderOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseLLMProviderOperation).toHaveBeenCalledWith({
    kind: "make-llm-primary",
    providerId: "provider-glm",
    requestBody: { expected_version: 1, reason: "提升 GLM 为本次主模型" },
  });
});

it("adds an OpenAI-compatible LLM without ever displaying a stored secret", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("模型设置");
  fireEvent.click(screen.getByRole("button", { name: "增加 LLM" }));
  fireEvent.change(screen.getByLabelText("供应商名称"), { target: { value: "backup-provider" } });
  fireEvent.change(screen.getByLabelText("模型 ID"), { target: { value: "backup-model" } });
  fireEvent.change(screen.getByLabelText("API 根地址"), { target: { value: "https://backup.example/v1" } });
  fireEvent.change(screen.getByLabelText("API Key"), { target: { value: "one-time-secret-value" } });
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "新增经过批准的备用供应商" } });
  fireEvent.click(screen.getByRole("button", { name: "保存设置" }));

  await waitFor(() => expect(executeEnterpriseLLMProviderOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseLLMProviderOperation).toHaveBeenCalledWith({
    kind: "create-llm-provider",
    requestBody: expect.objectContaining({
      name: "backup-provider",
      model: "backup-model",
      base_url: "https://backup.example/v1",
      api_key: "one-time-secret-value",
    }),
  });
});

it("offers MiMo primary and GLM fallback presets without filling a credential", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("\u6a21\u578b\u8bbe\u7f6e");
  fireEvent.click(screen.getByRole("button", { name: "\u589e\u52a0 LLM" }));

  fireEvent.click(screen.getByRole("button", { name: "\u4f7f\u7528 MiMo v2.5 \u4e3b\u6a21\u578b\u9884\u8bbe" }));
  expect(screen.getByLabelText("\u4f9b\u5e94\u5546\u540d\u79f0")).toHaveValue("mimo");
  expect(screen.getByLabelText("\u6a21\u578b ID")).toHaveValue("mimo-v2.5");
  expect(screen.getByLabelText("API \u6839\u5730\u5740")).toHaveValue("https://token-plan-cn.xiaomimimo.com/v1");
  expect(screen.getByLabelText("API Key")).toHaveValue("");
  expect(screen.getByLabelText("\u5c1d\u8bd5\u6b21\u6570")).toHaveValue(2);

  fireEvent.click(screen.getByRole("button", { name: "\u4f7f\u7528 GLM 5.2 \u5907\u7528\u9884\u8bbe" }));
  expect(screen.getByLabelText("\u4f9b\u5e94\u5546\u540d\u79f0")).toHaveValue("glm");
  expect(screen.getByLabelText("\u6a21\u578b ID")).toHaveValue("GLM-5.2");
  expect(screen.getByLabelText("API \u6839\u5730\u5740")).toHaveValue("https://chatapi.weixin.qq.com/openai/v1");
  expect(screen.getByLabelText("API Key")).toHaveValue("");
  expect(screen.getByLabelText("\u5c1d\u8bd5\u6b21\u6570")).toHaveValue(1);
});
it("renders tenant metrics and protects the current administrator controls", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  expect(await screen.findByText("Pharma R&D")).toBeInTheDocument();
  expect(screen.getByText("业务数据集")).toBeInTheDocument();
  await selectEnterpriseTab("用户与角色");
  expect(screen.getByRole("button", { name: "调整 Administrator 的角色" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "调整 Research Analyst 的角色" })).toBeEnabled();
});

it("keeps enterprise tabs keyboard reachable on narrow screens", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  const overview = await screen.findByRole("tab", { name: "租户概况" });
  const audit = screen.getByRole("tab", { name: "审计日志" });

  expect(overview).toHaveAttribute("aria-controls", "enterprise-panel-overview");
  expect(audit).toHaveAttribute("tabindex", "-1");

  overview.focus();
  fireEvent.keyDown(overview, { key: "End" });

  expect(audit).toHaveFocus();
  expect(audit).toHaveAttribute("aria-selected", "true");
  expect(audit).toHaveAttribute("aria-controls", "enterprise-panel-audit");
  expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "enterprise-tab-audit");
});

it("moves focus into a user action dialog and returns it to the trigger", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户与角色");
  const trigger = screen.getByRole("button", { name: "调整 Research Analyst 的角色" });
  trigger.focus();
  fireEvent.click(trigger);

  const dialog = await screen.findByRole("dialog", { name: "调整用户角色" });
  await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));

  fireEvent.click(screen.getByRole("button", { name: "关闭" }));
  await waitFor(() => expect(document.activeElement).toBe(trigger));
});

it("closes enterprise user dialogs with Escape and restores the trigger", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户与角色");
  const trigger = screen.getByRole("button", { name: "新建用户" });
  trigger.focus();
  fireEvent.click(trigger);
  await screen.findByRole("dialog");
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await waitFor(() => expect(trigger).toHaveFocus());
});

it("creates a local account through the versioned enterprise operation", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户与角色");
  fireEvent.click(screen.getByRole("button", { name: "新建用户" }));
  fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "new@example.test" } });
  fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "New Analyst" } });
  fireEvent.change(screen.getByLabelText("企业角色"), { target: { value: "analyst" } });
  fireEvent.change(screen.getByLabelText("初始密码"), { target: { value: "initial-password-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "创建用户" }));

  await waitFor(() => expect(executeEnterpriseOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseOperation).toHaveBeenCalledWith({
    kind: "create-user",
    requestBody: {
      email: "new@example.test",
      display_name: "New Analyst",
      role: "analyst",
      initial_password: "initial-password-2026",
      oidc_issuer: null,
      oidc_subject: null,
    },
  });
});

it("updates group membership with the displayed concurrency version", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户组");
  fireEvent.click(screen.getByRole("button", { name: "管理 Research Operations 的成员" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: /Administrator/ }));
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "Add tenant administrator" } });
  fireEvent.click(screen.getByRole("button", { name: "保存变更" }));

  await waitFor(() => expect(executeEnterpriseOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseOperation).toHaveBeenCalledWith({
    kind: "update-group-members",
    groupId: "group-1",
    requestBody: {
      expected_version: 1,
      user_ids: ["analyst-1", "admin-1"],
      reason: "Add tenant administrator",
    },
  });
});

it("does not retry a rejected administrative mutation", async () => {
  vi.mocked(executeEnterpriseOperation).mockRejectedValue(new Error("stale administrative version"));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("用户组");
  fireEvent.click(screen.getByRole("button", { name: "编辑 Research Operations" }));
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "Update team definition" } });
  fireEvent.click(screen.getByRole("button", { name: "保存变更" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("stale administrative version");
  expect(executeEnterpriseOperation).toHaveBeenCalledOnce();
});

it("governs datasets, remote sessions and MCP clients from one access view", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("访问与生命周期");
  expect(screen.getByRole("heading", { name: "数据集与交付授权" })).toBeInTheDocument();
  expect(screen.getByText("WEB / MCP")).toBeInTheDocument();
  const revokeButton = screen
    .getAllByRole("button", { name: "撤销" })
    .find((button) => !button.hasAttribute("disabled"));
  expect(revokeButton).toBeEnabled();

  fireEvent.click(revokeButton as HTMLButtonElement);
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "Remote device was retired" } });
  fireEvent.click(screen.getByRole("button", { name: "确认变更" }));
  await waitFor(() => expect(executeEnterpriseOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseOperation).toHaveBeenCalledWith({
    kind: "revoke-session",
    sessionId: "session-remote",
    requestBody: { reason: "Remote device was retired" },
  });
});

it("creates a scoped API key and clears its one-time secret after acknowledgement", async () => {
  vi.mocked(executeEnterpriseApiKeyOperation).mockResolvedValue({
    ...workspace.apiKeyCatalog.items[0],
    id: "key-created",
    name: "New Research Agent",
    prefix: "phk_created1",
    commercial_client_id: null,
    commercial_client_name: null,
    secret: "phk_one-time-secret",
  });
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("访问与生命周期");
  expect(screen.getByText("Research Agent Key")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "新建密钥" }));
  fireEvent.change(screen.getByLabelText("密钥名称"), { target: { value: "New Research Agent" } });
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "Approved integration onboarding" } });
  fireEvent.click(screen.getByRole("button", { name: "创建密钥" }));

  await waitFor(() => expect(executeEnterpriseApiKeyOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseApiKeyOperation).toHaveBeenCalledWith({
    kind: "create-api-key",
    requestBody: {
      name: "New Research Agent",
      scopes: workspace.apiKeyCatalog.allowed_scopes,
      expires_at: expect.any(String),
      reason: "Approved integration onboarding",
    },
  });
  const secretInput = await screen.findByLabelText("API 密钥");
  expect(secretInput).toHaveValue("phk_one-time-secret");
  await waitFor(() => expect(secretInput).toHaveFocus());
  expect((secretInput as HTMLInputElement).selectionStart).toBe(0);
  expect((secretInput as HTMLInputElement).selectionEnd).toBe("phk_one-time-secret".length);
  fireEvent.click(screen.getByRole("button", { name: "已安全保存" }));
  expect(screen.queryByDisplayValue("phk_one-time-secret")).not.toBeInTheDocument();
});

it("requires an explicit reason before revoking an active API key", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await selectEnterpriseTab("访问与生命周期");
  fireEvent.click(screen.getByRole("button", { name: "撤销 Research Agent Key" }));
  const confirm = screen.getByRole("button", { name: "确认撤销" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("变更原因"), { target: { value: "Credential compromise response" } });
  fireEvent.click(confirm);

  await waitFor(() => expect(executeEnterpriseApiKeyOperation).toHaveBeenCalledOnce());
  expect(executeEnterpriseApiKeyOperation).toHaveBeenCalledWith({
    kind: "revoke-api-key",
    keyId: "key-1",
    requestBody: { reason: "Credential compromise response" },
  });
});

it("separates live platform signals from external release evidence", async () => {
  renderWithQueryClient(<PlatformOperationsPanel platform={workspace.platform} />);
  expect(screen.getByRole("table", { name: "平台服务状态" })).toHaveTextContent("platform-operations");
  expect(screen.getByText("pharma-data-factory", { exact: true })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "平台 SLO" })).toHaveTextContent("web-availability");
  expect(screen.getByRole("table", { name: "平台发布证据" })).toHaveTextContent("backup_restore");
  expect(screen.getByText("fc5e8a1b3d72", { exact: true })).toBeInTheDocument();
});
