import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyPermissionBoundary({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  let loggedOut = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      if (loggedOut) return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
      return route.fulfill({
        json: {
          id: "browser-viewer",
          tenant_id: "browser-tenant",
          email: "viewer@example.test",
          display_name: "Browser Viewer",
          role: "viewer",
        },
      });
    }
    if (path === "/api/v1/auth/logout") {
      loggedOut = true;
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/entities") {
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 1,
          offset: 0,
          facets: {},
          suggestions: [],
          engine: "opensearch",
          took_ms: 1,
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/internal?view=governance");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByText("无权访问该工作区", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "AI 审核" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "数据工厂" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "商业运营" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "企业管理" })).toHaveCount(0);
  await page.getByRole("button", { name: "退出账号" }).click();
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await expect(page.getByRole("heading", { name: "内部管理工作台" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "医药情报工作台" })).toHaveCount(0);
}
