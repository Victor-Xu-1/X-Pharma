import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifySessionRecovery({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  let recovered = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") {
      return recovered
        ? route.fulfill({ json: { mode: "local" } })
        : route.fulfill({ status: 503, json: { detail: "Identity service unavailable" } });
    }
    if (path === "/api/v1/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "Authentication required" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await expect(page.getByText("Identity service unavailable", { exact: true })).toBeVisible();
  recovered = true;
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
}
