import { afterEach, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { loadSession } from "../lib/contracts/session";

afterEach(() => vi.restoreAllMocks());

function responseFor(path: string, config: Response, currentUser: Response): Response {
  return path.endsWith("/api/v1/auth/config") ? config : currentUser;
}

it("treats an unauthenticated current-user response as a valid logged-out session", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    responseFor(
      String(input),
      new Response(JSON.stringify({ mode: "local" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(loadSession()).resolves.toEqual({ mode: "local", user: null });
});

it("does not let a parallel 401 mask an authentication configuration outage", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    responseFor(
      String(input),
      new Response(JSON.stringify({ detail: "Identity provider unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json", "X-Request-ID": "auth-config-503" },
      }),
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(loadSession()).rejects.toEqual(new ApiError("Identity provider unavailable", 503, "auth-config-503"));
});

it("rejects unsupported authentication modes at the generated contract boundary", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
    responseFor(
      String(input),
      new Response(JSON.stringify({ mode: "saml" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  await expect(loadSession()).rejects.toThrow("不支持的登录模式");
});
