import { afterEach, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { loadSession } from "../lib/contracts/session";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

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

function pendingResponse(signal?: AbortSignal | null): Promise<Response> {
  return new Promise((_resolve, reject) => {
    signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  });
}

it("reports a configuration failure without waiting for a stalled current-user request, and cancels the sibling", async () => {
  vi.useFakeTimers();
  const cancellation = new AbortController();
  let userSignal: AbortSignal | null | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    if (String(input).endsWith("/api/v1/auth/config")) {
      return new Response(JSON.stringify({ detail: "Identity provider unavailable" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }
    userSignal = init?.signal;
    return pendingResponse(userSignal);
  });
  let failure: unknown;
  const result = loadSession(cancellation.signal).catch((error: unknown) => {
    failure = error;
  });
  try {
    await vi.advanceTimersByTimeAsync(0);
    expect(failure).toEqual(new ApiError("Identity provider unavailable", 503, null));
    expect(userSignal?.aborted).toBe(true);
  } finally {
    cancellation.abort();
    await result;
  }
});

it.each(["config", "me"])("bounds a stalled %s request and cancels it so retry starts fresh", async (stalled) => {
  vi.useFakeTimers();
  const cancellation = new AbortController();
  let stalledSignal: AbortSignal | null | undefined;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith(`/api/v1/auth/${stalled}`)) {
      stalledSignal = init?.signal;
      return pendingResponse(stalledSignal);
    }
    return responseFor(
      path,
      Response.json({ mode: "local" }),
      new Response(JSON.stringify({ detail: "Not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  let failure: unknown;
  const result = loadSession(cancellation.signal).catch((error: unknown) => {
    failure = error;
  });
  try {
    await vi.advanceTimersByTimeAsync(10_000);
    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).message).toContain("会话验证超时");
    expect(stalledSignal?.aborted).toBe(true);
    fetch.mockImplementation(async (input) =>
      responseFor(
        String(input),
        Response.json({ mode: "local" }),
        new Response(JSON.stringify({ detail: "Not authenticated" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(loadSession()).resolves.toEqual({ mode: "local", user: null });
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    cancellation.abort();
    await result;
  }
});

it("honors caller cancellation without converting it into a timeout or opening a logged-out session", async () => {
  vi.useFakeTimers();
  const cancellation = new AbortController();
  const signals: Array<AbortSignal | null | undefined> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    signals.push(init?.signal);
    return pendingResponse(init?.signal);
  });
  const result = loadSession(cancellation.signal);
  const rejected = expect(result).rejects.toMatchObject({ name: "CancelError" });
  await vi.advanceTimersByTimeAsync(0);
  cancellation.abort();
  await rejected;
  expect(signals).toHaveLength(2);
  expect(signals.every((signal) => signal?.aborted)).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});
