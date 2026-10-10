import { act, fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { changeCurrentUserPassword, updateCurrentUser } from "../lib/contracts/session";
import type { UserRead } from "../lib/generated";
import { setLocale } from "../lib/i18n";
import { hasPendingSessionWrites } from "../lib/organizationSession";
import { OverviewView } from "../views/OverviewView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/session", async (original) => ({
  ...(await original<typeof import("../lib/contracts/session")>()),
  updateCurrentUser: vi.fn(),
  changeCurrentUserPassword: vi.fn(),
}));
const user: UserRead = {
  id: "account-a",
  tenant_id: "organization-a",
  role: "admin",
  display_name: "Original researcher",
  email: "researcher@example.test",
  phone: null,
  avatar_url: null,
};
beforeEach(() => {
  vi.resetAllMocks();
});
function formFor(name: string) {
  const form = screen.getByRole("button", { name, exact: true }).closest("form");
  if (!form) throw new Error("The account form is missing");
  return form;
}

it("synchronously locks repeated profile submissions, related fields and account exit across locales", async () => {
  let finish: ((value: UserRead) => void) | undefined;
  vi.mocked(updateCurrentUser).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const onUserUpdated = vi.fn(),
    onLogout = vi.fn();
  renderWithQueryClient(
    <OverviewView user={user} authMode="local" onLogout={onLogout} onUserUpdated={onUserUpdated} />,
  );
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Unsaved original 科研" } });
  const form = formFor("保存个人资料");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  expect(updateCurrentUser).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("用户名")).toBeDisabled();
  expect(screen.getByLabelText("当前密码")).toBeDisabled();
  expect(screen.getByRole("button", { name: "退出当前账号" })).toBeDisabled();
  expect(hasPendingSessionWrites()).toBe(true);
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Display name")).toHaveValue("Unsaved original 科研");
  expect(updateCurrentUser).toHaveBeenCalledTimes(1);
  await act(async () => finish?.({ ...user, display_name: "Unsaved original 科研" }));
  expect(await screen.findByText("Profile updated.")).toBeInTheDocument();
  expect(screen.getByLabelText("Display name")).toBeEnabled();
  expect(hasPendingSessionWrites()).toBe(false);
  expect(onUserUpdated).toHaveBeenCalledTimes(1);
  expect(onLogout).not.toHaveBeenCalled();
});

it("keeps password credentials out of mutation history and captures one immutable submission", async () => {
  let finish: (() => void) | undefined;
  vi.mocked(changeCurrentUserPassword).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const { queryClient } = renderWithQueryClient(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "controlled-current-password" } });
  fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "controlled-next-password" } });
  fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "controlled-next-password" } });
  const form = formFor("修改密码");
  act(() => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  expect(changeCurrentUserPassword).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("用户名")).toBeDisabled();
  expect(queryClient.getMutationCache().getAll()).toEqual([]);
  act(() => setLocale("en"));
  expect(screen.getByLabelText("Current password")).toHaveValue("controlled-current-password");
  expect(changeCurrentUserPassword).toHaveBeenCalledWith({
    current_password: "controlled-current-password",
    new_password: "controlled-next-password",
  });
  await act(async () => finish?.());
  expect(screen.getByLabelText("Current password")).toHaveValue("");
  expect(screen.getByLabelText("New password")).toHaveValue("");
  expect(hasPendingSessionWrites()).toBe(false);
});

it("does not publish a late profile response after the account page unmounts", async () => {
  let finish: ((value: UserRead) => void) | undefined;
  vi.mocked(updateCurrentUser).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const onUserUpdated = vi.fn();
  const { unmount } = renderWithQueryClient(
    <OverviewView user={user} onLogout={vi.fn()} onUserUpdated={onUserUpdated} />,
  );
  fireEvent.submit(formFor("保存个人资料"));
  unmount();
  await act(async () => finish?.({ ...user, display_name: "Late response" }));
  expect(onUserUpdated).not.toHaveBeenCalled();
  expect(hasPendingSessionWrites()).toBe(false);
});

it("retains a rejected draft, sanitizes a private server failure and translates the feedback in place", async () => {
  vi.mocked(updateCurrentUser).mockRejectedValue(new ApiError("private database location", 500, null));
  renderWithQueryClient(<OverviewView user={user} onLogout={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Rejected source draft" } });
  fireEvent.submit(formFor("保存个人资料"));
  await screen.findByText("个人资料保存失败");
  expect(screen.queryByText("private database location")).not.toBeInTheDocument();
  act(() => setLocale("en"));
  expect(screen.getByRole("alert")).toHaveTextContent("Could not save your profile.");
  expect(screen.getByLabelText("Display name")).toHaveValue("Rejected source draft");
  fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "Controlled new draft" } });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(updateCurrentUser).toHaveBeenCalledTimes(1);
});

it("rejects a successful profile response that belongs to a different identity", async () => {
  vi.mocked(updateCurrentUser).mockResolvedValue({ ...user, id: "other-account" });
  const onUserUpdated = vi.fn();
  renderWithQueryClient(<OverviewView user={user} onLogout={vi.fn()} onUserUpdated={onUserUpdated} />);
  fireEvent.submit(formFor("保存个人资料"));
  await screen.findByRole("alert");
  expect(onUserUpdated).not.toHaveBeenCalled();
  expect(screen.getByLabelText("用户名")).toHaveValue(user.display_name);
});

it("does not render a password echoed in a credential error", async () => {
  vi.mocked(changeCurrentUserPassword).mockRejectedValue(
    new ApiError("Rejected controlled-current-password", 400, null),
  );
  renderWithQueryClient(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "controlled-current-password" } });
  fireEvent.change(screen.getByLabelText("新密码"), { target: { value: "controlled-next-password" } });
  fireEvent.change(screen.getByLabelText("确认新密码"), { target: { value: "controlled-next-password" } });
  fireEvent.submit(formFor("修改密码"));
  expect(await screen.findByRole("alert")).toHaveTextContent("密码修改失败");
  expect(screen.getByRole("alert")).not.toHaveTextContent("controlled-current-password");
});

it("removes local password drafts when enterprise identity takes ownership", () => {
  const { rerender } = renderWithQueryClient(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("当前密码"), { target: { value: "controlled-current-password" } });
  rerender(<OverviewView user={user} authMode="oidc" onLogout={vi.fn()} />);
  expect(screen.queryByLabelText("当前密码")).not.toBeInTheDocument();
  rerender(<OverviewView user={user} authMode="local" onLogout={vi.fn()} />);
  expect(screen.getByLabelText("当前密码")).toHaveValue("");
  expect(changeCurrentUserPassword).not.toHaveBeenCalled();
});
