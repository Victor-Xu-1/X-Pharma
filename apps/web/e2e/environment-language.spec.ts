import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { environmentLanguageFixture } from "./fixtures/environment-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[environment-language] preserves report truth, plan lifecycle, drafts and cached reads without executing installation", async ({
  page,
}, testInfo) => {
  const fixture = environmentLanguageFixture();
  let environmentReads = 0,
    platformReads = 0,
    plans = 0;
  let releasePlan: (() => void) | undefined;
  const writes: string[] = [],
    errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals" && request.method() === "POST")
      return route.fulfill({ status: 202, json: {} });
    if (path === "/api/v1/enterprise/environment/plans" && request.method() === "POST") {
      plans++;
      if (plans === 1) {
        expect(request.postDataJSON()).toEqual({ recipe_id: "frontend-dependencies", offline: true });
        await new Promise<void>((resolve) => {
          releasePlan = resolve;
        });
        return route.fulfill({ json: fixture.plan });
      }
      return route.fulfill({ status: 400, json: { detail: "原始计划错误 — controlled browser fixture" } });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-environment-user",
          tenant_id: "controlled-environment-tenant",
          email: "environment@example.test",
          display_name: "Controlled browser fixture",
          role: "admin",
        },
      });
    if (path === "/api/v1/enterprise/environment") {
      environmentReads++;
      return route.fulfill({ json: fixture.environment });
    }
    if (path === "/api/v1/enterprise/platform") {
      platformReads++;
      return route.fulfill({ json: fixture.platform });
    }
    return route.fulfill({ json: [] });
  });
  async function audit(name: string) {
    expect(
      (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
    ).toEqual([]);
    const bounds = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth,
      viewport: document.documentElement.clientWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false, animations: "disabled" });
  }
  await page.goto("/workspace/internal?view=environment");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const probes = page.getByRole("table", { name: "Gateway dependency versions", exact: true });
  await expect(probes).toContainText("Not verified");
  await expect(probes).not.toContainText("Meets declared requirements");
  await expect(probes).toContainText("原始探针诊断 / controlled fixture");
  await audit("runtime-unverified-en");
  await page.getByRole("tab", { name: "Installation and repair", exact: true }).click();
  await page.getByRole("button", { name: "Prepare installation plan", exact: true }).click();
  await expect(page.getByRole("button", { name: "Preparing…", exact: true })).toBeDisabled();
  await expect(page.getByRole("radio", { name: "Frontend dependencies", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Refresh status", exact: true })).toBeDisabled();
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("button", { name: "正在生成…", exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: "环境检测", exact: true }).click();
  await page.getByRole("tab", { name: "安装与修复", exact: true }).click();
  await expect(page.getByRole("checkbox")).toBeChecked();
  await expect(page.getByRole("checkbox")).toBeDisabled();
  await audit("plan-pending-zh");
  expect(releasePlan).toBeDefined();
  releasePlan?.();
  await expect(page.getByRole("heading", { name: "安装计划已生成，尚未执行", exact: true })).toBeVisible();
  await selectInterfaceLanguage(page, "en");
  await expect(
    page.getByRole("heading", { name: "Installation plan prepared, not executed", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Prepared installation plan", exact: true })).toContainText(
    fixture.plan.commands[0].join(" "),
  );
  await expect(page.getByRole("button", { name: "Execute installation", exact: true })).toHaveCount(0);
  await audit("plan-prepared-en");
  await page.getByRole("tab", { name: "Runtime and release evidence", exact: true }).click();
  const queueCount = page.locator(".platform-queue-metrics > div").first();
  await expect(queueCount).toContainText("Not observed");
  await expect(page.locator(".platform-queue-metrics > div").nth(3)).toContainText("0");
  await audit("unobserved-queues-en");
  await page.getByRole("tab", { name: "Installation and repair", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Installation plan prepared, not executed", exact: true }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Python dependencies", exact: true }).check();
  await page.getByRole("button", { name: "Prepare installation plan", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("原始计划错误 — controlled browser fixture");
  await expect(page.getByRole("region", { name: "Prepared installation plan", exact: true })).toHaveCount(0);
  await audit("plan-error-en");
  expect(plans).toBe(2);
  expect(environmentReads).toBe(1);
  expect(platformReads).toBe(1);
  expect(writes).toEqual([]);
});
