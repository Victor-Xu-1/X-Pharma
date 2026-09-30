import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginScreen } from "../components/LoginScreen";
import { ApiError } from "../lib/api";
import { login } from "../lib/contracts/session";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/session", () => ({ login: vi.fn() }));

const loginMock = vi.mocked(login);

function renderLogin(workbench: "research" | "internal" = "research") {
  return renderWithQueryClient(<LoginScreen mode="local" workbench={workbench} onLogin={vi.fn()} />);
}

function submitCredentials() {
  const email = screen.getByLabelText("工作邮箱");
  const password = screen.getByLabelText("密码");
  fireEvent.change(email, { target: { value: "nobody@example.invalid" } });
  fireEvent.change(password, { target: { value: "invalid-password-for-smoke-test" } });
  fireEvent.click(screen.getByRole("button", { name: "进入工作台" }));
  return { email, password };
}

describe("LoginScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each(["research", "internal"] as const)("uses the supplied X-Pharma logo in the %s login", (workbench) => {
    renderLogin(workbench);
    const mark = document.querySelector(".brand-symbol");
    const image = mark?.querySelector("img");
    expect(image).toHaveAttribute("src", expect.stringContaining("X-Pharma-logo-128.png"));
    expect(image).toHaveAttribute("alt", "");
    expect(mark).toHaveAttribute("aria-hidden", "true");
    expect(mark?.querySelector("svg")).toBeNull();
    expect(screen.getByText("X-Pharma")).toBeInTheDocument();
  });

  it("keeps the public login shell free of internal workspace language", () => {
    renderLogin();

    expect(screen.getByRole("region", { name: "X-Pharma" })).toBeInTheDocument();
    expect(screen.getByText("生物医药研发情报平台")).toBeInTheDocument();
    expect(screen.getByText("医药情报工作台")).toBeInTheDocument();
    expect(screen.getByText("专业数据检索与关联分析")).toBeInTheDocument();
    expect(screen.queryByText("Enterprise Research Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("AUTHORIZED ACCESS")).not.toBeInTheDocument();
    expect(screen.queryByText("Controlled workspace · v0.1")).not.toBeInTheDocument();
    expect(screen.queryByText("HUMAN WORKSPACE")).not.toBeInTheDocument();

    expect(screen.getByLabelText("工作邮箱")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("密码")).toHaveAttribute("autocomplete", "current-password");
  });

  it("presents the separate internal login identity without engineering language", () => {
    renderLogin("internal");

    expect(screen.getByRole("region", { name: "内部管理平台" })).toBeInTheDocument();
    expect(screen.getByText("数据治理与运营管理")).toBeInTheDocument();
    expect(screen.getByText("内部管理")).toBeInTheDocument();
    expect(screen.getByText("仅限授权内部人员")).toBeInTheDocument();
    expect(screen.getByText("管理员登录")).toBeInTheDocument();
    expect(screen.queryByText("Internal Management Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("INTERNAL ACCESS")).not.toBeInTheDocument();
    expect(screen.queryByText("Controlled workspace · v0.1")).not.toBeInTheDocument();
    expect(screen.queryByText("HUMAN WORKSPACE")).not.toBeInTheDocument();
  });

  it.each(["research", "internal"] as const)(
    "only enables the %s local login when both credentials are complete",
    (workbench) => {
      renderLogin(workbench);

      const email = screen.getByLabelText("工作邮箱");
      const password = screen.getByLabelText("密码");
      const submit = screen.getByRole("button", { name: "进入工作台" });

      expect(submit).toBeDisabled();
      fireEvent.change(email, { target: { value: "analyst@example.test" } });
      expect(submit).toBeDisabled();
      fireEvent.change(password, { target: { value: "short" } });
      expect(submit).toBeDisabled();
      fireEvent.change(password, { target: { value: "valid-password" } });
      expect(submit).toBeEnabled();
      fireEvent.change(email, { target: { value: "   " } });
      expect(submit).toBeDisabled();
    },
  );

  it.each([
    [new ApiError("Invalid credentials", 401, null), "邮箱或密码不正确，请检查后重试"],
    [new ApiError("Rate limited", 429, null), "尝试次数过多，请稍后重试"],
    [new ApiError("Identity provider unavailable", 503, null), "登录服务暂时不可用，请稍后重试"],
    [new Error("Network detail"), "登录失败，请稍后重试"],
  ])("sanitizes login failures and clears the password", async (failure, message) => {
    loginMock.mockRejectedValueOnce(failure);
    renderLogin();

    const { email, password } = submitCredentials();

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
    expect(email).toHaveValue("nobody@example.invalid");
    expect(password).toHaveValue("");
    expect(email).toHaveAttribute("aria-describedby", "login-error");
    expect(password).toHaveAttribute("aria-describedby", "login-error");
    expect(screen.queryByText(failure.message)).not.toBeInTheDocument();
  });

  it.each(["research", "internal"] as const)(
    "returns focus to the %s password field after rejected button submission",
    async (workbench) => {
      loginMock.mockRejectedValueOnce(new ApiError("Invalid credentials", 401, null));
      renderLogin(workbench);
      const { password } = submitCredentials();

      await screen.findByRole("alert");

      expect(password).toHaveValue("");
      expect(password).toHaveFocus();
    },
  );

  it("clears a stale login error when credentials are edited", async () => {
    loginMock.mockRejectedValueOnce(new ApiError("Invalid credentials", 401, null));
    renderLogin();
    submitCredentials();

    await screen.findByRole("alert");
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "new-password" } });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("工作邮箱")).not.toHaveAttribute("aria-describedby");
    expect(screen.getByLabelText("密码")).not.toHaveAttribute("aria-describedby");
  });
});
