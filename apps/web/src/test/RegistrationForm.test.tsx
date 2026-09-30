import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginScreen } from "../components/LoginScreen";
import { ApiError } from "../lib/api";
import { registerAccount, registrationPolicy } from "../lib/contracts/accounts";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/accounts", () => ({ registerAccount: vi.fn(), registrationPolicy: vi.fn() }));

function openRegistration(workbench: "research" | "internal" = "research") {
  renderWithQueryClient(<LoginScreen mode="local" workbench={workbench} onLogin={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "注册" }));
}

function fillRegistration(password = "registration-test-password") {
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "New User" } });
  fireEvent.change(screen.getByLabelText("注册邮箱"), { target: { value: "new@example.test" } });
  fireEvent.change(screen.getByLabelText("设置密码"), { target: { value: password } });
  fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: password } });
}

describe("shared workbench account registration", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(registrationPolicy).mockResolvedValue({
      research: "independent",
      internal: "invitation",
      password_min_length: 12,
    });
    vi.mocked(registerAccount).mockResolvedValue({
      id: "new",
      tenant_id: "personal",
      email: "new@example.test",
      display_name: "New User",
      role: "viewer",
      phone: null,
      avatar_url: null,
    });
  });

  it("shows a usable login/register switch in each entrance", async () => {
    openRegistration();
    await screen.findByLabelText("注册邮箱");
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建账号" })).toBeDisabled();
    expect(screen.queryByLabelText("管理员邀请码")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
    expect(screen.getByRole("heading", { name: "账户登录" })).toBeInTheDocument();
  });

  it("rejects mismatched passwords without a request", async () => {
    openRegistration();
    await screen.findByLabelText("注册邮箱");
    fillRegistration();
    fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "different-password" } });
    fireEvent.click(screen.getByRole("button", { name: "创建账号" }));
    expect(screen.getByRole("alert")).toHaveTextContent("两次输入的密码不一致");
    expect(registerAccount).not.toHaveBeenCalled();
  });

  it("requires an administrator invite in the internal entrance", async () => {
    openRegistration("internal");
    await screen.findByLabelText("管理员邀请码");
    fillRegistration();
    expect(screen.getByRole("button", { name: "创建账号" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("管理员邀请码"), { target: { value: "one-time-test-invitation" } });
    expect(screen.getByRole("button", { name: "创建账号" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "创建账号" }));
    await waitFor(() =>
      expect(vi.mocked(registerAccount).mock.calls[0]?.[0]).toEqual(
        expect.objectContaining({ workbench: "internal", invitation_code: "one-time-test-invitation" }),
      ),
    );
  });

  it("returns to login after registration and never retains the password", async () => {
    vi.mocked(registerAccount).mockResolvedValue({
      id: "new",
      tenant_id: "personal",
      email: "new@example.test",
      display_name: "New User",
      role: "viewer",
      phone: null,
      avatar_url: null,
    });
    openRegistration();
    await screen.findByLabelText("注册邮箱");
    fillRegistration();
    fireEvent.click(screen.getByRole("button", { name: "创建账号" }));
    await screen.findByRole("heading", { name: "账户登录" });
    expect(screen.getByRole("status")).toHaveTextContent("注册成功");
    expect(screen.getByLabelText("工作邮箱")).toHaveValue("new@example.test");
    expect(screen.getByLabelText("密码")).toHaveValue("");
    expect(vi.mocked(registerAccount).mock.calls[0]?.[0]).toEqual(expect.objectContaining({ workbench: "research" }));
  });

  it("sanitizes server failures and clears secret fields", async () => {
    vi.mocked(registerAccount).mockRejectedValue(new ApiError("Private internal stack", 500, null));
    openRegistration();
    await screen.findByLabelText("注册邮箱");
    fillRegistration();
    fireEvent.click(screen.getByRole("button", { name: "创建账号" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("注册服务暂不可用");
    expect(screen.getByLabelText("设置密码")).toHaveValue("");
    expect(screen.getByLabelText("确认密码")).toHaveValue("");
    expect(screen.queryByText("Private internal stack")).not.toBeInTheDocument();
  });

  it("reports disabled enterprise identity registration without password fallback", async () => {
    vi.mocked(registrationPolicy).mockResolvedValue({ research: "disabled", internal: "disabled" });
    openRegistration("internal");
    expect(await screen.findByText(/当前账号由组织身份系统/)).toBeInTheDocument();
    expect(screen.queryByLabelText("设置密码")).not.toBeInTheDocument();
  });
});
