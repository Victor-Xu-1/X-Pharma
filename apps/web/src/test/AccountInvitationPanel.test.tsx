import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountInvitationPanel } from "../components/AccountInvitationPanel";
import { useAccountInvitations } from "../components/accountInvitations/useAccountInvitations";
import { ApiError } from "../lib/api";
import { accountInvitations, issueAccountInvitation, revokeAccountInvitation } from "../lib/contracts/accounts";
import type { AuthMode } from "../lib/contracts/session";
import type { InvitationRead } from "../lib/generated";
import { useEnterpriseOperationBoundary } from "../views/enterprise/useEnterpriseOperationBoundary";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/accounts", () => ({
  accountInvitations: vi.fn(),
  issueAccountInvitation: vi.fn(),
  revokeAccountInvitation: vi.fn(),
}));

const invitation: InvitationRead = {
  id: "test-invitation",
  tenant_id: "test-tenant",
  email: "employee@example.test",
  created_at: "2026-10-01T00:00:00Z",
  expires_at: "2026-10-02T00:00:00Z",
  claimed_at: null,
  revoked_at: null,
  status: "active",
};

function InvitationHarness({ authMode = "local" }: { authMode?: AuthMode }) {
  const boundary = useEnterpriseOperationBoundary();
  const workspace = useAccountInvitations(authMode, true, boundary);
  return <AccountInvitationPanel workspace={workspace} />;
}

describe("administrator account invitations", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(accountInvitations).mockResolvedValue([]);
    vi.mocked(issueAccountInvitation).mockResolvedValue({ invitation, code: "one-time-fixture-code" });
    vi.mocked(revokeAccountInvitation).mockResolvedValue(undefined);
  });

  it("shows the empty state and rejects an out-of-range expiry", async () => {
    renderWithQueryClient(<InvitationHarness />);
    await screen.findByText("暂无注册邀请");
    expect(screen.getByRole("button", { name: "生成注册邀请码" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("受邀邮箱"), { target: { value: "employee@example.test" } });
    fireEvent.change(screen.getByLabelText("有效小时"), { target: { value: "169" } });
    expect(screen.getByRole("button", { name: "生成注册邀请码" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("有效小时"), { target: { value: "1.5" } });
    expect(screen.getByRole("button", { name: "生成注册邀请码" })).toBeDisabled();
    expect(issueAccountInvitation).not.toHaveBeenCalled();
  });

  it("shows the code once, traps focus, and clears it from the mutation cache on close", async () => {
    const { queryClient } = renderWithQueryClient(<InvitationHarness />);
    await screen.findByText("暂无注册邀请");
    const submit = screen.getByRole("button", { name: "生成注册邀请码" });
    fireEvent.change(screen.getByLabelText("受邀邮箱"), { target: { value: "employee@example.test" } });
    submit.focus();
    fireEvent.click(submit);
    const dialog = await screen.findByRole("dialog", { name: "新生成的注册邀请码" });
    expect(within(dialog).getByLabelText("一次性邀请码")).toHaveValue("one-time-fixture-code");
    await waitFor(() => expect(within(dialog).getByLabelText("一次性邀请码")).toHaveFocus());
    expect(vi.mocked(issueAccountInvitation).mock.calls[0]?.[0]).toEqual({
      email: "employee@example.test",
      valid_hours: 24,
    });
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(submit).toHaveFocus());
    expect(
      JSON.stringify(
        queryClient
          .getMutationCache()
          .getAll()
          .map((mutation) => mutation.state.data),
      ),
    ).not.toContain("one-time-fixture-code");
  });

  it("only revokes active invitations and refreshes their persisted state", async () => {
    vi.mocked(accountInvitations).mockResolvedValue([
      invitation,
      { ...invitation, id: "used", email: "used@example.test", status: "consumed", claimed_at: "2026-10-01T01:00:00Z" },
    ]);
    renderWithQueryClient(<InvitationHarness />);
    const table = await screen.findByRole("table", { name: "注册邀请记录" });
    const buttons = within(table).getAllByRole("button", { name: "撤销邀请" });
    expect(buttons[0]).toBeEnabled();
    expect(buttons[1]).toBeDisabled();
    vi.mocked(accountInvitations).mockResolvedValue([
      { ...invitation, status: "revoked", revoked_at: "2026-10-01T01:00:00Z" },
    ]);
    const activeButton = buttons[0];
    if (!activeButton) throw new Error("Active invitation revoke button is missing");
    fireEvent.click(activeButton);
    await waitFor(() => expect(vi.mocked(revokeAccountInvitation).mock.calls[0]?.[0]).toBe(invitation.id));
    await waitFor(() => expect(screen.getByRole("button", { name: "撤销邀请" })).toBeDisabled());
  });

  it("allows retry after a list failure and sanitizes failed issue responses", async () => {
    vi.mocked(accountInvitations).mockRejectedValueOnce(new Error("private database stack"));
    vi.mocked(issueAccountInvitation).mockRejectedValue(new ApiError("private provider response", 500, null));
    renderWithQueryClient(<InvitationHarness />);
    await screen.findByText("注册邀请读取失败");
    fireEvent.click(screen.getByRole("button", { name: /重试/ }));
    await screen.findByText("暂无注册邀请");
    fireEvent.change(screen.getByLabelText("受邀邮箱"), { target: { value: "employee@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "生成注册邀请码" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("邀请操作失败，请稍后重试");
    expect(screen.queryByText(/private/)).not.toBeInTheDocument();
  });

  it("does not expose a password registration alternative to enterprise identity users", () => {
    renderWithQueryClient(<InvitationHarness authMode="oidc" />);
    expect(screen.getByRole("status")).toHaveTextContent("组织身份系统");
    expect(accountInvitations).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "生成注册邀请码" })).not.toBeInTheDocument();
  });

  it("does not reveal an issued one-time code when current invitation reconciliation denies access", async () => {
    vi.mocked(accountInvitations)
      .mockResolvedValueOnce([])
      .mockRejectedValue(new ApiError("Access denied", 403, null));
    const { queryClient } = renderWithQueryClient(<InvitationHarness />);
    await screen.findByText("暂无注册邀请");
    fireEvent.change(screen.getByLabelText("受邀邮箱"), { target: { value: "employee@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "生成注册邀请码" }));
    await screen.findByText("注册邀请读取失败");
    await waitFor(() =>
      expect(screen.getByLabelText("受邀邮箱").closest("form")).toHaveAttribute("aria-busy", "false"),
    );
    expect(screen.queryByRole("dialog", { name: "新生成的注册邀请码" })).not.toBeInTheDocument();
    expect(
      JSON.stringify(
        queryClient
          .getMutationCache()
          .getAll()
          .map((item) => item.state),
      ),
    ).not.toContain("one-time-fixture-code");
    expect(screen.getByRole("button", { name: "生成注册邀请码" })).toBeDisabled();
  });
});
