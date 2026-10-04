import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyComparisonExport({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  const setId = "22222222-2222-4222-8222-222222222222";
  const entity = {
    id: "11111111-1111-4111-8111-111111111111",
    entity_type: "target",
    name: "EGFR",
    description: "Epidermal growth factor receptor",
    external_ids: { uniprot: "P00533" },
    attributes: {},
    review_status: "verified",
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  const emptySet = {
    id: setId,
    owner_user_id: "comparison-user",
    name: "EGFR competitive landscape",
    description: "",
    visibility: "tenant",
    version: 1,
    member_count: 0,
    editable: true,
    members: [],
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  let detail: Record<string, unknown> = emptySet;
  let exportRequested = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "comparison-user",
          tenant_id: "comparison-tenant",
          email: "comparison@example.test",
          display_name: "Comparison Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/comparison-sets/catalog" && request.method() === "GET") {
      expect(url.searchParams.get("limit")).toBe("25");
      expect(url.searchParams.get("offset")).toBe("0");
      return route.fulfill({ json: { items: [detail], total: 1, limit: 25, offset: 0 } });
    }
    if (path === `/api/v1/comparison-sets/${setId}` && request.method() === "GET")
      return route.fulfill({ json: detail });
    if (path === "/api/v1/workspace/export-policy") {
      return route.fulfill({
        json: {
          id: "policy-browser-1",
          policy_version: "browser-v1",
          enabled: true,
          allowed_formats: ["json", "xlsx"],
          allowed_fields: ["position", "id", "entity_type", "name", "external_ids"],
          max_records_per_export: 20,
          attribution: "Internal browser acceptance",
          configured_by_user_id: "browser-admin",
          policy_sha256: "a".repeat(64),
          created_at: "2026-07-18T10:00:00Z",
          updated_at: "2026-07-18T10:00:00Z",
        },
      });
    }
    if (path === "/api/v1/entities" && request.method() === "GET") {
      return route.fulfill({
        json: {
          items: [entity],
          total: 1,
          limit: 25,
          offset: 0,
          facets: {},
          suggestions: [],
          engine: "opensearch",
          took_ms: 1,
        },
      });
    }
    if (path === `/api/v1/comparison-sets/${setId}/members` && request.method() === "POST") {
      detail = {
        ...emptySet,
        version: 2,
        member_count: 1,
        members: [
          {
            id: "member-browser-1",
            position: 0,
            added_by_user_id: "comparison-user",
            created_at: "2026-07-18T10:00:00Z",
            entity,
          },
        ],
      };
      return route.fulfill({ json: detail });
    }
    if (path === `/api/v1/comparison-sets/${setId}/export` && request.method() === "POST") {
      exportRequested = true;
      return route.fulfill({
        body: JSON.stringify({ schema: "pharma.workspace-comparison-export.v1", records: [entity] }),
        contentType: "application/json",
        headers: { "Content-Disposition": `attachment; filename="comparison-${setId}-v2.json"` },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/?view=collections");
  await expect(page.getByRole("heading", { name: "对比列表" })).toBeVisible();
  await expect(page.getByText("工作台导出策略", { exact: true })).toHaveCount(0);
  await expect(page.getByText("租户导出策略", { exact: true })).toHaveCount(0);
  await page.getByLabel("搜索要加入的药物、靶点、机构或适应症").fill("EGFR");
  await page.getByRole("button", { name: "检索", exact: true }).click();
  await page.getByRole("button", { name: "加入 EGFR" }).click();
  await expect(page.getByText("UNIPROT: P00533", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出", exact: true }).click();
  const artifact = await download;
  expect(artifact.suggestedFilename()).toBe(`comparison-${setId}-v2.json`);
  await expect.poll(() => exportRequested).toBe(true);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
