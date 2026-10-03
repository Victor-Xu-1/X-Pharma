import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionBoundary } from "../components/SessionBoundary";
import { ApiError } from "../lib/api";
import { loadSession, logout } from "../lib/contracts/session";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/session", () => ({
  loadSession: vi.fn(),
  logout: vi.fn(),
  login: vi.fn(),
  sessionKeys: { current: ["session", "current"] },
}));
const user = {
  id: "user",
  tenant_id: "tenant",
  email: "fixture@example.test",
  display_name: "Fixture",
  role: "admin" as const,
};

function renderSession() {
  return renderWithQueryClient(
    <SessionBoundary workbench="research">
      {(session) => (
        <>
          <p>{session.user.display_name}</p>
          <button type="button" onClick={session.logout} disabled={session.logoutPending}>
            退出账号
          </button>
          {session.logoutError ? <p role="alert">{session.logoutError}</p> : null}
        </>
      )}
    </SessionBoundary>,
    undefined,
    (client) => client.setQueryData(["private", "records"], ["private record"]),
  );
}

describe("shared account logout", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(loadSession).mockResolvedValue({ mode: "local", user });
    window.history.replaceState(null, "", "/workspace/research?view=target&entity=private-id");
  });

  it("preserves the account and private cache after a failed logout, and offers retry", async () => {
    vi.mocked(logout).mockRejectedValueOnce(new ApiError("Internal server detail", 503, null));
    const { queryClient } = renderSession();
    await screen.findByText("Fixture");
    fireEvent.click(screen.getByRole("button", { name: "退出账号" }));
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("Fixture")).toBeInTheDocument());
    expect(await screen.findByRole("alert")).toHaveTextContent("退出失败，请重试");
    expect(screen.queryByText("Internal server detail")).not.toBeInTheDocument();
    expect(queryClient.getQueryData(["private", "records"])).toEqual(["private record"]);
    vi.mocked(logout).mockResolvedValueOnce(undefined);
    fireEvent.click(screen.getByRole("button", { name: "退出账号" }));
    await screen.findByRole("heading", { name: "账户登录" });
    expect(queryClient.getQueryData(["private", "records"])).toBeUndefined();
    expect(window.location.pathname + window.location.search).toBe("/workspace/research");
  });

  it("treats an already expired session as signed out", async () => {
    vi.mocked(logout).mockRejectedValueOnce(new ApiError("Expired", 401, null));
    renderSession();
    await screen.findByText("Fixture");
    fireEvent.click(screen.getByRole("button", { name: "退出账号" }));
    await screen.findByRole("heading", { name: "账户登录" });
  });

  it("shows an initial session error once and uses an explicit retry even when ordinary queries retry automatically", async () => {
    vi.mocked(loadSession).mockRejectedValueOnce(new Error("会话验证超时，请检查服务连接后重试"));
    renderWithQueryClient(
      <SessionBoundary workbench="research">{(session) => <p>{session.user.display_name}</p>}</SessionBoundary>,
      undefined,
      (client) => client.setDefaultOptions({ queries: { retry: 2, retryDelay: 0 } }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("会话验证超时");
    expect(loadSession).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("正在验证会话")).not.toBeInTheDocument();
    expect(screen.queryByText("Fixture")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await screen.findByText("Fixture");
    expect(loadSession).toHaveBeenCalledTimes(2);
  });
});
