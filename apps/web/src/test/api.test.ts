import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../lib/api";

describe("API client", () => {
  beforeEach(() => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement the Cookie Store API used by browsers.
    document.cookie = "pharma_csrf=test-csrf";
  });

  it("adds CSRF protection to mutating requests", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } }),
      );
    await api.post("/api/example", { value: 1 });
    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    expect(init?.credentials).toBe("same-origin");
  });

  it("returns a diagnostic API error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid input" }), {
        status: 422,
        headers: { "Content-Type": "application/json", "X-Request-ID": "request-1" },
      }),
    );
    await expect(api.get("/api/example")).rejects.toEqual(new ApiError("Invalid input", 422, "request-1"));
  });
});
