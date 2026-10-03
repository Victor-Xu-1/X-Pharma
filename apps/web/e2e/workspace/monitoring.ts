import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyMonitoring(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(60_000);
  let acknowledged = false;
  let savedSearchVisibility: "private" | "tenant" = "tenant";
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "monitoring-user",
          tenant_id: "monitoring-tenant",
          email: "monitoring@example.test",
          display_name: "Monitoring Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/monitoring/saved-searches" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "saved-browser-1",
            owner_user_id: "monitoring-user",
            name: "EGFR enterprise watch",
            description: "Shared target watch",
            query_type: "entity_search",
            query_version: 2,
            query_json: { q: "EGFR", entity_type: "target" },
            visibility: savedSearchVisibility,
            created_at: "2026-07-18T10:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/saved-searches/saved-browser-1" && request.method() === "PATCH") {
      const body = request.postDataJSON() as { visibility: "private" | "tenant" };
      savedSearchVisibility = body.visibility;
      return route.fulfill({
        json: {
          id: "saved-browser-1",
          owner_user_id: "monitoring-user",
          name: "EGFR enterprise watch",
          description: "Shared target watch",
          query_type: "entity_search",
          query_version: 2,
          query_json: { q: "EGFR", entity_type: "target" },
          visibility: savedSearchVisibility,
          created_at: "2026-07-18T10:00:00Z",
          updated_at: "2026-07-18T12:05:00Z",
        },
      });
    }
    if (path === "/api/v1/monitoring/topics") {
      return route.fulfill({
        json: [
          {
            id: "topic-browser-1",
            owner_user_id: "monitoring-user",
            saved_search_id: "saved-browser-1",
            query_version: 2,
            name: "EGFR changes",
            active: true,
            created_at: "2026-07-18T10:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/alerts" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "alert-browser-1",
            topic_id: "topic-browser-1",
            topic_name: "EGFR changes",
            entity_id: "entity-browser-1",
            entity_name: "EGFR",
            event_type: "governance.fact.published",
            title: "EGFR changed",
            summary: "target 实体 EGFR 匹配监控条件。",
            payload_json: { query_version: 2 },
            occurred_at: "2026-07-18T12:00:00Z",
            read_at: acknowledged ? "2026-07-18T12:01:00Z" : null,
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/alerts/alert-browser-1/read" && request.method() === "POST") {
      acknowledged = true;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=monitoring");
  await expect(page.getByRole("heading", { name: "情报监控与变更提醒" })).toBeVisible();
  await expect(page.getByText("EGFR changes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "将 EGFR 提醒标记已读" }).click();
  await expect.poll(() => acknowledged).toBe(true);
  await expect(page.getByText("read", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page.getByText("EGFR enterprise watch", { exact: true })).toBeVisible();
  await expect(page.getByText("企业共享", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "将 EGFR enterprise watch 设为私有" }).click();
  await expect.poll(() => savedSearchVisibility).toBe("private");
  await expect(page.getByText("仅自己", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page.getByText("仅自己", { exact: true })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
