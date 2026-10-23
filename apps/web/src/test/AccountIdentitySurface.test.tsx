import { act, fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { updateCurrentUser } from "../lib/contracts/session";
import { setLocale } from "../lib/i18n";
import { OverviewView } from "../views/OverviewView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/session", async (original) => ({
  ...(await original<typeof import("../lib/contracts/session")>()),
  updateCurrentUser: vi.fn(),
  changeCurrentUserPassword: vi.fn(),
}));
const user = {
  id: "identity-a",
  tenant_id: "organization-a",
  role: "admin" as const,
  display_name: "Original researcher 科研",
  email: "original@example.test",
  phone: null,
  avatar_url: null,
};
beforeEach(() => {
  vi.resetAllMocks();
});

it("does not invent account standing or repeat an identity eyebrow from a status-free User response", () => {
  renderWithQueryClient(<OverviewView user={user} onLogout={vi.fn()} />);
  expect(screen.getByRole("heading", { name: user.display_name })).toBeInTheDocument();
  expect(screen.getByText(user.email)).toBeInTheDocument();
  expect(screen.queryByText("账户正常")).not.toBeInTheDocument();
  expect(screen.queryByText("账户信息")).not.toBeInTheDocument();
});

it("keeps unverified email visible while full recovery guidance is initially collapsed and keyboard-readable", () => {
  renderWithQueryClient(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  expect(screen.getByText("邮箱归属未验证。")).toBeVisible();
  const summary = screen.getByText("登录与恢复说明", { selector: "summary" });
  const details = summary.closest("details");
  expect(details).not.toHaveAttribute("open");
  const guidance = screen.getByText(/本地账号：邮箱仅作为登录标识/);
  expect(guidance).not.toBeVisible();
  fireEvent.click(summary);
  expect(details).toHaveAttribute("open");
  expect(guidance).toBeVisible();
  expect(screen.getByLabelText("当前密码")).toBeInTheDocument();
  expect(updateCurrentUser).not.toHaveBeenCalled();
});

it("retains the open identity disclosure and an original profile draft during in-place language switching", () => {
  renderWithQueryClient(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Unsubmitted original 科研" } });
  fireEvent.click(screen.getByText("登录与恢复说明", { selector: "summary" }));
  const details = screen.getByText("登录与恢复说明", { selector: "summary" }).closest("details");
  act(() => setLocale("en"));
  expect(screen.getByText("Email ownership is unverified.")).toBeVisible();
  expect(screen.getByText("Sign-in & recovery", { selector: "summary" }).closest("details")).toBe(details);
  expect(details).toHaveAttribute("open");
  expect(screen.getByLabelText("Display name")).toHaveValue("Unsubmitted original 科研");
  expect(screen.getByRole("heading", { name: user.display_name })).toBeInTheDocument();
  expect(updateCurrentUser).not.toHaveBeenCalled();
});

it("identifies enterprise sign-in without suggesting local email or password ownership", () => {
  renderWithQueryClient(<OverviewView user={user} authMode="oidc" onLogout={vi.fn()} />);
  expect(screen.getByText("登录与恢复由企业身份服务管理。")).toBeVisible();
  expect(screen.queryByText("邮箱归属未验证。")).not.toBeInTheDocument();
  expect(screen.getByLabelText("邮箱")).toHaveAttribute("readonly");
  expect(screen.queryByLabelText("当前密码")).not.toBeInTheDocument();
});
