import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { contractRequest } from "../lib/contract";
import { CancelError, DataFactoryService, WorkspaceExportsService } from "../lib/generated";

describe("generated OpenAPI transport", () => {
  beforeEach(() => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement the browser Cookie Store API.
    document.cookie = "pharma_csrf=contract-csrf";
  });

  it("adds CSRF, same-origin credentials and a typed JSON body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "source-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await DataFactoryService.createDataSourceApiV1AdminDataSourcesPost({
      requestBody: {
        authorization_scopes: ["contract:test"],
        dataset_key: "literature",
        name: "Literature",
        owner: "Data Operations",
        root_uri: "/sources/literature",
      },
    });

    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("contract-csrf");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(init?.credentials).toBe("same-origin");
    expect(JSON.parse(String(init?.body))).toEqual(expect.objectContaining({ dataset_key: "literature" }));
  });

  it("preserves API diagnostics and emits the unauthorized session event", async () => {
    const unauthorized = vi.fn();
    window.addEventListener("pharma:unauthorized", unauthorized, { once: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Session expired" }), {
        status: 401,
        headers: { "Content-Type": "application/json", "X-Request-ID": "request-contract-1" },
      }),
    );

    await expect(DataFactoryService.listDataSourcesApiV1AdminDataSourcesGet()).rejects.toEqual(
      new ApiError("Session expired", 401, "request-contract-1"),
    );
    expect(unauthorized).toHaveBeenCalledOnce();
  });

  it("bridges React Query AbortSignal cancellation to the generated transport", async () => {
    let transportSignal: AbortSignal | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          transportSignal = init?.signal ?? undefined;
          transportSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), {
            once: true,
          });
        }),
    );
    const controller = new AbortController();
    const result = contractRequest(DataFactoryService.listDataSourcesApiV1AdminDataSourcesGet(), controller.signal);
    await vi.waitFor(() => expect(transportSignal).toBeDefined());

    controller.abort();

    await expect(result).rejects.toBeInstanceOf(CancelError);
    expect(transportSignal?.aborted).toBe(true);
  });

  it("does not broadcast a stale unauthorized response after cancellation", async () => {
    const unauthorized = vi.fn();
    window.addEventListener("pharma:unauthorized", unauthorized);
    let resolveFetch: ((response: Response) => void) | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );

    const result = DataFactoryService.listDataSourcesApiV1AdminDataSourcesGet();
    await vi.waitFor(() => expect(resolveFetch).toBeDefined());
    result.cancel();
    resolveFetch?.(
      new Response(JSON.stringify({ detail: "Session expired" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(result).rejects.toBeInstanceOf(CancelError);
    expect(unauthorized).not.toHaveBeenCalled();
    window.removeEventListener("pharma:unauthorized", unauthorized);
  });

  it("preserves binary export responses as Blob instances", async () => {
    const bytes = new Uint8Array([0x50, 0x4b, 0x03, 0x04]);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(bytes, {
        status: 200,
        headers: { "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      }),
    );

    const result = await WorkspaceExportsService.exportComparisonSetApiV1ComparisonSetsComparisonSetIdExportPost({
      comparisonSetId: "22222222-2222-4222-8222-222222222222",
      requestBody: {
        expected_version: 1,
        export_format: "xlsx",
        fields: ["id", "entity_type", "name"],
        idempotency_key: "33333333-3333-4333-8333-333333333333",
      },
    });

    expect(result).toMatchObject({
      size: bytes.byteLength,
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    expect(new Uint8Array(await result.arrayBuffer())).toEqual(bytes);
  });
});
