import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyWorkspaceStates({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  let releaseSearch: (() => void) | undefined;
  const blockedSearch = new Promise<void>((resolve) => {
    releaseSearch = resolve;
  });
  let searchAttempts = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-analyst",
          tenant_id: "browser-tenant",
          email: "analyst@example.test",
          display_name: "Browser Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/entities") {
      searchAttempts += 1;
      if (searchAttempts === 1) {
        await blockedSearch;
      }
      if (searchAttempts <= 3) return route.fulfill({ status: 503, json: { detail: "Search backend unavailable" } });
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 100,
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

  await page.goto("/?view=explorer&q=EGFR&type=target");
  await expect(page.getByText("正在检索结构化情报", { exact: true })).toBeVisible();
  releaseSearch?.();
  await expect(page.getByText("Search backend unavailable", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByText("未找到匹配实体", { exact: true })).toBeVisible();
  await expect(page.getByLabel("情报检索词")).toHaveValue("EGFR");
  await expect(page.getByRole("button", { name: /对象类型：靶点/ })).toHaveAttribute("aria-pressed", "true");
}
