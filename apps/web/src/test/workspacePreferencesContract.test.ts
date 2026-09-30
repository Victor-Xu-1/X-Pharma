import { expect, it, vi } from "vitest";

import { loadWorkspaceTablePreference, saveWorkspaceTablePreference } from "../lib/contracts/workspacePreferences";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

it("loads and normalizes an account-scoped table preference", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      column_order: ["phase", "title"],
      column_visibility: { phase: false },
      density: "compact",
      persisted: true,
      preference_key: "pipeline",
      schema_version: 1,
      updated_at: "2026-07-29T04:00:00Z",
      version: 7,
    }),
  );

  await expect(loadWorkspaceTablePreference("pipeline")).resolves.toEqual({
    columnOrder: ["phase", "title"],
    columnVisibility: { phase: false },
    density: "compact",
    persisted: true,
    preferenceKey: "pipeline",
    updatedAt: "2026-07-29T04:00:00Z",
    version: 7,
  });
});

it("rebases one stale write against the latest server version without unbounded retries", async () => {
  const requests: Array<{ body: Record<string, unknown> | null; method: string }> = [];
  let putCount = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
    requests.push({ body, method });
    if (method === "GET") {
      return json({
        column_order: [],
        column_visibility: {},
        density: "comfortable",
        persisted: true,
        preference_key: "deals",
        schema_version: 1,
        updated_at: "2026-07-29T04:00:00Z",
        version: 4,
      });
    }
    putCount += 1;
    if (putCount === 1) return json({ detail: "Table preference version is stale" }, 409);
    return json({
      column_order: ["amount", "title"],
      column_visibility: { amount: false },
      density: "compact",
      persisted: true,
      preference_key: "deals",
      schema_version: 1,
      updated_at: "2026-07-29T04:01:00Z",
      version: 5,
    });
  });

  const saved = await saveWorkspaceTablePreference(
    "deals",
    {
      columnOrder: ["amount", "title"],
      columnVisibility: { amount: false },
      density: "compact",
    },
    2,
  );

  expect(saved.version).toBe(5);
  expect(requests.map(({ method }) => method)).toEqual(["PUT", "GET", "PUT"]);
  expect(requests[0]?.body?.expected_version).toBe(2);
  expect(requests[2]?.body?.expected_version).toBe(4);
});

it("rejects a malformed preference response at the frontend boundary", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    json({
      column_order: ["unsafe column"],
      column_visibility: {},
      density: "comfortable",
      persisted: false,
      preference_key: "entity-search",
      schema_version: 1,
      version: 0,
    }),
  );

  await expect(loadWorkspaceTablePreference("entity-search")).rejects.toThrow("Invalid table preference column order");
});
