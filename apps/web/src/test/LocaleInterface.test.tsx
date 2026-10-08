import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { LoginScreen } from "../components/LoginScreen";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { registerAccount, registrationPolicy } from "../lib/contracts/accounts";
import { login, updateCurrentUser } from "../lib/contracts/session";
import { setLocale } from "../lib/i18n";
import { OverviewView } from "../views/OverviewView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/accounts", () => ({ registerAccount: vi.fn(), registrationPolicy: vi.fn() }));
vi.mock("../lib/contracts/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/contracts/session")>()),
  login: vi.fn(),
  updateCurrentUser: vi.fn(),
  changeCurrentUserPassword: vi.fn(),
}));

const user = {
  id: "preview",
  tenant_id: "own",
  role: "admin" as const,
  display_name: "研究员 EGFR",
  email: "preview@example.test",
};
function switchLanguage(value: "zh-CN" | "en") {
  fireEvent.change(screen.getByRole("combobox", { name: /界面语言|Interface language/ }), { target: { value } });
}

beforeEach(() => {
  setLocale("zh-CN");
  vi.mocked(registrationPolicy).mockResolvedValue({
    research: "independent",
    internal: "invitation",
    password_min_length: 12,
  });
});
afterEach(() => {
  setLocale("zh-CN");
});

it.each(["research", "internal"] as const)(
  "switches the %s login in place without submitting or losing the email draft",
  (workbench) => {
    renderWithQueryClient(<LoginScreen mode="local" workbench={workbench} onLogin={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("工作邮箱"), { target: { value: "researcher@example.test" } });
    switchLanguage("en");
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Work email")).toHaveValue("researcher@example.test");
    expect(screen.getByRole("button", { name: "Open workbench" })).toBeDisabled();
    expect(login).not.toHaveBeenCalled();
    switchLanguage("zh-CN");
    expect(screen.getByLabelText("工作邮箱")).toHaveValue("researcher@example.test");
  },
);

it.each(["research", "internal"] as const)(
  "preserves %s registration fields when the locale changes",
  async (workbench) => {
    renderWithQueryClient(<LoginScreen mode="local" workbench={workbench} onLogin={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "注册" }));
    await screen.findByLabelText("用户名");
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "中文研究员" } });
    fireEvent.change(screen.getByLabelText("注册邮箱"), { target: { value: "register@example.test" } });
    switchLanguage("en");
    expect(screen.getByLabelText("Display name")).toHaveValue("中文研究员");
    expect(screen.getByLabelText("Registration email")).toHaveValue("register@example.test");
    expect(
      screen.getByRole("heading", {
        name: workbench === "internal" ? "Register with an invitation" : "Create an independent account",
      }),
    ).toBeInTheDocument();
    expect(registrationPolicy).toHaveBeenCalledTimes(1);
    expect(registerAccount).not.toHaveBeenCalled();
  },
);

it("keeps an invitation's consent state while translating its safety explanation", () => {
  renderWithQueryClient(<LoginScreen mode="local" workbench="research" onLogin={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "加入组织" }));
  fireEvent.click(screen.getByRole("checkbox"));
  switchLanguage("en");
  expect(screen.getByRole("checkbox")).toBeChecked();
  expect(
    screen.getByText("I agree to join the invited organization without sharing my original organization's data."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Verify account and join" })).toBeDisabled();
});

it.each(["research", "internal"] as const)(
  "translates %s navigation without changing permissions, identity, URL or cached results",
  (workbench) => {
    window.history.replaceState(
      null,
      "",
      `/workspace/${workbench}?view=${workbench === "research" ? "overview" : "factory"}&q=EGFR`,
    );
    const originalUrl = window.location.href;
    const { queryClient } = renderWithQueryClient(
      <WorkspaceShell
        user={user}
        activeWorkbench={workbench}
        activeView={workbench === "research" ? "overview" : "factory"}
        onView={vi.fn()}
        onLogout={vi.fn()}
      >
        <OverviewView user={user} authMode="local" onLogout={vi.fn()} />
      </WorkspaceShell>,
    );
    const results = { drug: "奥希替尼", target: "EGFR", quote: "原始中文证据" };
    queryClient.setQueryData(["untouched-research"], results);
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "未保存中文草稿 EGFR" } });
    switchLanguage("en");
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    expect(screen.getByLabelText("Display name")).toHaveValue("未保存中文草稿 EGFR");
    expect(screen.getByText("研究员 EGFR", { selector: "h2" })).toBeInTheDocument();
    expect(window.location.href).toBe(originalUrl);
    expect(queryClient.getQueryData(["untouched-research"])).toBe(results);
    expect(updateCurrentUser).not.toHaveBeenCalled();
  },
);

it("updates an already-visible validation message when switching languages", async () => {
  renderWithQueryClient(<LoginScreen mode="local" workbench="research" onLogin={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "注册" }));
  await screen.findByLabelText("用户名");
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "..." } });
  const form = screen.getByRole("button", { name: "创建账号" }).closest("form");
  if (!form) throw new Error("Registration form is missing");
  fireEvent.submit(form);
  expect(screen.getByRole("alert")).toHaveTextContent("用户名至少包含一个文字或数字");
  switchLanguage("en");
  expect(screen.getByRole("alert")).toHaveTextContent("Your display name must contain at least one letter or number.");
  expect(registerAccount).not.toHaveBeenCalled();
});

it("announces blocked preference persistence without preventing English switching or changing the draft", () => {
  renderWithQueryClient(<LoginScreen mode="local" workbench="research" onLogin={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("工作邮箱"), { target: { value: "draft@example.test" } });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Blocked preference storage", "SecurityError");
  });
  switchLanguage("en");
  expect(screen.getByRole("status")).toHaveTextContent("your browser did not allow saving it");
  expect(screen.getByLabelText("Work email")).toHaveValue("draft@example.test");
  expect(login).not.toHaveBeenCalled();
});
