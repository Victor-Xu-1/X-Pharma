import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { accountInvitations, issueAccountInvitation } from "../lib/contracts/accounts";
import {
  enterpriseKeys,
  executeEnterpriseApiKeyOperation,
  executeEnterpriseOperation,
  loadEnterpriseAccess,
  loadEnterpriseAudit,
  loadEnterpriseGroups,
  loadEnterpriseModels,
  loadEnterpriseOverview,
  loadEnterpriseUsers,
} from "../lib/contracts/enterprise";
import { setLocale } from "../lib/i18n";
import { EnterpriseView } from "../views/EnterpriseView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/enterprise", async (original) => ({
  ...(await original<typeof import("../lib/contracts/enterprise")>()),
  executeEnterpriseApiKeyOperation: vi.fn(),
  executeEnterpriseOperation: vi.fn(),
  loadEnterpriseOverview: vi.fn(),
  loadEnterpriseGroups: vi.fn(),
  loadEnterpriseUsers: vi.fn(),
  loadEnterpriseAccess: vi.fn(),
  loadEnterpriseModels: vi.fn(),
  loadEnterpriseAudit: vi.fn(),
}));
vi.mock("../lib/contracts/accounts", async (original) => ({
  ...(await original<typeof import("../lib/contracts/accounts")>()),
  accountInvitations: vi.fn(),
  issueAccountInvitation: vi.fn(),
}));
const user = {
  id: "controlled-admin",
  tenant_id: "controlled-organization",
  email: "admin@example.test",
  display_name: "Original administrator <source>",
  role: "admin" as const,
};
const time = "2026-10-11T00:00:00Z";
const access = {
  datasets: [],
  sessions: [],
  clients: [],
  retentionPolicies: [],
  legalHolds: [],
  apiKeyCatalog: {
    required_scope: "mcp:connect",
    allowed_scopes: ["mcp:connect", "entities:read"],
    min_ttl_hours: 1,
    max_ttl_days: 366,
    items: [],
  },
};
beforeEach(() => {
  vi.resetAllMocks();
  setLocale("zh-CN");
  vi.mocked(loadEnterpriseOverview).mockResolvedValue({
    tenant: {
      id: user.tenant_id,
      slug: "original-organization",
      name: "Original organization <source>",
      active: true,
      created_at: time,
      updated_at: time,
    },
    user_count: 1,
    active_user_count: 1,
    admin_count: 1,
    group_count: 0,
    active_group_count: 0,
    dataset_count: 0,
    active_source_count: 0,
    audit_event_count_24h: 0,
  });
  vi.mocked(loadEnterpriseGroups).mockResolvedValue([]);
  vi.mocked(loadEnterpriseUsers).mockResolvedValue([]);
  vi.mocked(loadEnterpriseAccess).mockResolvedValue(access);
  vi.mocked(loadEnterpriseModels).mockResolvedValue([]);
  vi.mocked(accountInvitations).mockResolvedValue([]);
  vi.mocked(loadEnterpriseAudit).mockResolvedValue({ items: [], next_cursor: null });
});
it("does not present a previous audit page under new actor filters while that read is pending", async () => {
  vi.mocked(loadEnterpriseAudit)
    .mockResolvedValueOnce({
      items: [
        {
          id: "old-event",
          action: "OLD_AUDIT_ACTION",
          actor_id: "Original actor",
          actor_type: "user",
          details: {},
          occurred_at: time,
          outcome: "success",
          request_id: "Original request",
          resource_id: null,
          resource_type: "Original resource",
        },
      ],
      next_cursor: "ORIGINAL_CURSOR",
    })
    .mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "审计日志" }));
  await screen.findByText("OLD_AUDIT_ACTION");
  fireEvent.change(screen.getByRole("combobox", { name: "操作者类型" }), { target: { value: "agent" } });
  await waitFor(() => expect(loadEnterpriseAudit).toHaveBeenCalledTimes(2));
  expect(screen.queryByText("OLD_AUDIT_ACTION")).not.toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "操作者类型" })).toHaveValue("agent");
});
it("renders all seven enterprise panels in English while preserving the original organization name", async () => {
  setLocale("en");
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  for (const name of [
    "Organization overview",
    "Users & roles",
    "Registration invitations",
    "Groups",
    "Access & lifecycle",
    "Models",
    "Audit log",
  ])
    expect(await screen.findByRole("tab", { name })).toBeInTheDocument();
  expect(await screen.findByText("Original organization <source>")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "Registration invitations" }));
  expect(await screen.findByRole("heading", { name: "Internal registration invitations" })).toBeInTheDocument();
});
async function openGroup() {
  fireEvent.click(await screen.findByRole("tab", { name: "用户组" }));
  fireEvent.click(await screen.findByRole("button", { name: "新建用户组" }));
  const dialog = screen.getByRole("dialog", { name: "新建用户组" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "用户组名称" }), {
    target: { value: "Original group <source>" },
  });
  return dialog;
}
it("freezes group drafts, close and conflicting tabs until the captured request is settled", async () => {
  vi.mocked(executeEnterpriseOperation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  const dialog = await openGroup();
  fireEvent.click(within(dialog).getByRole("button", { name: "创建用户组" }));
  await waitFor(() => expect(executeEnterpriseOperation).toHaveBeenCalledOnce());
  expect(within(dialog).getByRole("textbox", { name: "用户组名称" })).toBeDisabled();
  expect(within(dialog).getByRole("button", { name: "关闭" })).toBeDisabled();
  expect(screen.getByRole("tab", { name: "用户与角色" })).toBeDisabled();
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(dialog).toBeInTheDocument();
});
it("captures one synchronous group submission before a same-tick duplicate can execute", async () => {
  vi.mocked(executeEnterpriseOperation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  const dialog = await openGroup();
  const form = within(dialog).getByRole("button", { name: "创建用户组" }).closest("form");
  if (!form) throw new Error("Group form missing");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await waitFor(() => expect(executeEnterpriseOperation).toHaveBeenCalledOnce());
});
it("includes invitation issuance in the same synchronous workspace boundary without changing its captured email", async () => {
  vi.mocked(issueAccountInvitation).mockImplementation(() => new Promise(() => {}));
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "注册邀请" }));
  await screen.findByText("暂无注册邀请");
  const email = screen.getByRole("textbox", { name: "受邀邮箱" });
  fireEvent.change(email, { target: { value: "original@example.test" } });
  const form = screen.getByRole("button", { name: "生成注册邀请码" }).closest("form");
  if (!form) throw new Error("Invitation form missing");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  await waitFor(() => expect(issueAccountInvitation).toHaveBeenCalledOnce());
  expect(email).toBeDisabled();
  expect(screen.getByRole("tab", { name: "用户组" })).toBeDisabled();
  expect(vi.mocked(issueAccountInvitation).mock.calls[0]?.[0]).toEqual({
    email: "original@example.test",
    valid_hours: 24,
  });
});
it("preserves the unsubmitted invitation draft across enterprise tabs and locale changes without issuing it", async () => {
  renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "注册邀请" }));
  await screen.findByText("暂无注册邀请");
  fireEvent.change(screen.getByRole("textbox", { name: "受邀邮箱" }), {
    target: { value: "Draft.original@example.test" },
  });
  fireEvent.change(screen.getByRole("spinbutton", { name: "有效小时" }), { target: { value: "72" } });
  fireEvent.click(screen.getByRole("tab", { name: "用户组" }));
  await act(async () => setLocale("en"));
  fireEvent.click(screen.getByRole("tab", { name: "Registration invitations" }));
  expect(await screen.findByRole("textbox", { name: "Invited email" })).toHaveValue("Draft.original@example.test");
  expect(screen.getByRole("spinbutton", { name: "Validity (hours)" })).toHaveValue(72);
  expect(issueAccountInvitation).not.toHaveBeenCalled();
});
it("does not keep one-time API secrets in the generic mutation cache after closing their only display", async () => {
  vi.mocked(executeEnterpriseApiKeyOperation).mockResolvedValue({
    id: "controlled-key",
    name: "Original key",
    prefix: "controlled-prefix",
    secret: "CONTROLLED_ONE_TIME_SECRET",
    active: true,
    status: "active",
    scopes: access.apiKeyCatalog.allowed_scopes,
    created_at: time,
    updated_at: time,
    expires_at: "2099-10-01T00:00:00Z",
    last_used_at: null,
    revoked_at: null,
    commercial_client_id: null,
    commercial_client_name: null,
  });
  const { queryClient } = renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "访问与生命周期" }));
  fireEvent.click(await screen.findByRole("button", { name: "新建密钥" }));
  const dialog = screen.getByRole("dialog", { name: "新建 Agent API 密钥" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "密钥名称" }), { target: { value: "Original key" } });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "变更原因" }), {
    target: { value: "Original reason <source>" },
  });
  fireEvent.click(within(dialog).getByRole("button", { name: "创建密钥" }));
  const secret = await screen.findByRole("dialog", { name: "立即保存 API 密钥" });
  fireEvent.click(within(secret).getByRole("button", { name: "已安全保存" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(
    JSON.stringify(
      queryClient
        .getMutationCache()
        .getAll()
        .map((mutation) => mutation.state),
    ),
  ).not.toContain("CONTROLLED_ONE_TIME_SECRET");
});
it("removes an opened group intent after the authoritative group read denies access", async () => {
  const { queryClient } = renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  await openGroup();
  vi.mocked(loadEnterpriseGroups).mockRejectedValue(new ApiError("RAW_ENTERPRISE_DENIAL", 403, null));
  await act(() => queryClient.refetchQueries({ queryKey: enterpriseKeys.groups, exact: true }));
  expect(await screen.findByRole("alert")).toHaveTextContent("RAW_ENTERPRISE_DENIAL");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(executeEnterpriseOperation).not.toHaveBeenCalled();
});
it("does not reopen a one-time API key after denied access is restored", async () => {
  vi.mocked(executeEnterpriseApiKeyOperation).mockResolvedValue({
    id: "controlled-key",
    name: "Original key",
    prefix: "controlled-prefix",
    secret: "CONTROLLED_ONE_TIME_SECRET",
    active: true,
    status: "active",
    scopes: access.apiKeyCatalog.allowed_scopes,
    created_at: time,
    updated_at: time,
    expires_at: "2099-10-01T00:00:00Z",
    last_used_at: null,
    revoked_at: null,
    commercial_client_id: null,
    commercial_client_name: null,
  });
  const { queryClient } = renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "访问与生命周期" }));
  fireEvent.click(await screen.findByRole("button", { name: "新建密钥" }));
  const form = screen.getByRole("dialog", { name: "新建 Agent API 密钥" });
  fireEvent.change(within(form).getByRole("textbox", { name: "密钥名称" }), { target: { value: "Original key" } });
  fireEvent.change(within(form).getByRole("textbox", { name: "变更原因" }), { target: { value: "Original reason" } });
  fireEvent.click(within(form).getByRole("button", { name: "创建密钥" }));
  await screen.findByDisplayValue("CONTROLLED_ONE_TIME_SECRET");
  vi.mocked(loadEnterpriseAccess).mockRejectedValue(new ApiError("Access denied", 403, null));
  await act(async () => {
    await queryClient.invalidateQueries({ queryKey: enterpriseKeys.access });
  });
  await waitFor(() => expect(screen.queryByDisplayValue("CONTROLLED_ONE_TIME_SECRET")).not.toBeInTheDocument());
  await act(async () => {
    queryClient.setQueryData(enterpriseKeys.access, access);
  });
  await waitFor(() => expect(screen.queryByText("Access denied")).not.toBeInTheDocument());
  expect(screen.queryByDisplayValue("CONTROLLED_ONE_TIME_SECRET")).not.toBeInTheDocument();
  expect(
    JSON.stringify(
      queryClient
        .getMutationCache()
        .getAll()
        .map((item) => item.state),
    ),
  ).not.toContain("CONTROLLED_ONE_TIME_SECRET");
});
it("keeps an edited group draft but does not send it against a changed authoritative revision", async () => {
  const group = {
    id: "current-group",
    tenant_id: user.tenant_id,
    name: "Original group",
    description: "Original description",
    active: true,
    version: 1,
    member_ids: [],
    member_count: 0,
    created_at: time,
    updated_at: time,
  };
  vi.mocked(loadEnterpriseGroups).mockResolvedValue([group]);
  const { queryClient } = renderWithQueryClient(<EnterpriseView user={user} authMode="local" />);
  fireEvent.click(await screen.findByRole("tab", { name: "用户组" }));
  fireEvent.click(await screen.findByRole("button", { name: "编辑 Original group" }));
  const dialog = screen.getByRole("dialog", { name: "编辑用户组" });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "用户组名称" }), {
    target: { value: "Unsubmitted group draft" },
  });
  fireEvent.change(within(dialog).getByRole("textbox", { name: "变更原因" }), { target: { value: "Original reason" } });
  await act(async () => queryClient.setQueryData(enterpriseKeys.groups, [{ ...group, version: 2 }]));
  fireEvent.click(within(dialog).getByRole("button", { name: "保存变更" }));
  expect(executeEnterpriseOperation).not.toHaveBeenCalled();
  expect(within(dialog).getByRole("textbox", { name: "用户组名称" })).toHaveValue("Unsubmitted group draft");
  expect(within(dialog).getByRole("alert")).toHaveTextContent("记录已变更，请重新核对当前记录后提交。");
});
