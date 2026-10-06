import { fireEvent, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { changeCurrentUserPassword, updateCurrentUser } from "../lib/contracts/session";
import type { User } from "../lib/types";
import { OverviewView } from "../views/OverviewView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/session", async () => {
  const actual = await vi.importActual<typeof import("../lib/contracts/session")>("../lib/contracts/session");
  return {
    ...actual,
    changeCurrentUserPassword: vi.fn(),
    updateCurrentUser: vi.fn(),
  };
});

const user: User = {
  id: "analyst-1",
  tenant_id: "tenant-internal-1",
  email: "analyst@example.test",
  display_name: "Analyst Chen",
  role: "analyst",
};

function renderOverview(overrides: Partial<ComponentProps<typeof OverviewView>> = {}) {
  return renderWithQueryClient(<OverviewView user={user} onLogout={vi.fn()} {...overrides} />);
}

beforeEach(() => {
  vi.mocked(updateCurrentUser).mockReset();
  vi.mocked(changeCurrentUserPassword).mockReset();
});

it("keeps enterprise identity recovery out of the local password path", () => {
  renderOverview({ authMode: "oidc" });
  expect(screen.getByLabelText("邮箱")).toHaveAttribute("readonly");
  expect(screen.queryByLabelText("当前密码")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "修改密码" })).not.toBeInTheDocument();
  expect(screen.getByText(/本软件不会接收或修改企业密码/)).toBeInTheDocument();
});

it("does not imply local email ownership has been verified", () => {
  renderOverview({ authMode: "local" });
  expect(screen.getByText(/尚未验证邮箱归属/)).toBeInTheDocument();
});

it("keeps the user center focused on account management", () => {
  renderOverview();

  expect(screen.getByRole("heading", { name: "Analyst Chen" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "个人资料" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "登录安全" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "账户操作" })).toBeInTheDocument();
  expect(screen.getByText("analyst@example.test")).toBeInTheDocument();
  expect(screen.getByText("账户正常")).toBeInTheDocument();
  expect(screen.queryByText(/最近访问|最近更新专题|知识专题|快捷入口|可查询数据/)).not.toBeInTheDocument();
  expect(screen.queryByText(/租户|治理状态|权限角色/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "退出当前账号" })).toBeInTheDocument();
});

it("persists profile fields through the session contract", async () => {
  const onUserUpdated = vi.fn();
  vi.mocked(updateCurrentUser).mockResolvedValue({
    ...user,
    display_name: "Updated Chen",
    email: "updated@example.test",
    phone: "13800000000",
    avatar_url: "https://cdn.example.test/avatar.png",
  });
  renderOverview({ onUserUpdated });

  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Updated Chen" } });
  fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "updated@example.test" } });
  fireEvent.change(screen.getByLabelText("电话"), { target: { value: "13800000000" } });
  fireEvent.change(screen.getByLabelText("头像图片地址"), {
    target: { value: "https://cdn.example.test/avatar.png" },
  });
  fireEvent.click(screen.getByRole("button", { name: "保存个人资料" }));

  expect(await screen.findByText("个人资料已更新")).toBeInTheDocument();
  expect(updateCurrentUser).toHaveBeenCalledWith({
    display_name: "Updated Chen",
    email: "updated@example.test",
    phone: "13800000000",
    avatar_url: "https://cdn.example.test/avatar.png",
  });
  expect(onUserUpdated).toHaveBeenCalledOnce();
});

it("rejects a corrupted display name before sending it to the server", async () => {
  renderOverview();

  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "???????????" } });
  fireEvent.click(screen.getByRole("button", { name: "保存个人资料" }));

  expect(await screen.findByText("用户名至少需要包含一个文字或数字")).toBeInTheDocument();
  expect(updateCurrentUser).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Victor" } });
  expect(screen.queryByText("用户名至少需要包含一个文字或数字")).not.toBeInTheDocument();
});

it("validates and persists password changes", async () => {
  vi.mocked(changeCurrentUserPassword).mockResolvedValue(undefined);
  renderOverview();

  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "old-password" } });
  fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "new-password-2026" } });
  fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "different-password" } });
  fireEvent.click(screen.getByRole("button", { name: "修改密码" }));
  expect(await screen.findByText("两次输入的新密码不一致")).toBeInTheDocument();
  expect(changeCurrentUserPassword).not.toHaveBeenCalled();

  fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "new-password-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "修改密码" }));
  expect(await screen.findByText("密码已修改，其他登录会话已退出")).toBeInTheDocument();
  expect(changeCurrentUserPassword).toHaveBeenCalledWith({
    current_password: "old-password",
    new_password: "new-password-2026",
  });
});

it("keeps logout inside account operations", () => {
  const onLogout = vi.fn();
  renderOverview({ onLogout });

  fireEvent.click(screen.getByRole("button", { name: "退出当前账号" }));
  expect(onLogout).toHaveBeenCalledOnce();
});
