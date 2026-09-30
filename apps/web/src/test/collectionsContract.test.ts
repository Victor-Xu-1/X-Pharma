import { afterEach, expect, it, vi } from "vitest";

import { getWorkspaceExportPolicy } from "../lib/contracts/collections";

afterEach(() => vi.restoreAllMocks());

it("maps an absent tenant export policy to null without hiding other failures", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Policy not configured" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await expect(getWorkspaceExportPolicy()).resolves.toBeNull();
});

it("rejects unsupported formats returned by a compromised or incompatible policy service", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "policy-1",
        policy_version: "workspace-export-v2",
        enabled: true,
        allowed_formats: ["exe"],
        allowed_fields: ["id", "entity_type", "name"],
        max_records_per_export: 20,
        attribution: "Internal use",
        configured_by_user_id: "user-1",
        policy_sha256: "a".repeat(64),
        created_at: "2026-07-18T10:00:00Z",
        updated_at: "2026-07-18T10:00:00Z",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  await expect(getWorkspaceExportPolicy()).rejects.toThrow("不支持的文件格式");
});
