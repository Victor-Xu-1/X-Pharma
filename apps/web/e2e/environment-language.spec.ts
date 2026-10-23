import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { environmentLanguageFixture } from "./fixtures/environment-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[environment-language] keeps a compact narrow heading and separates dependency facts from visible identity uncertainty", async ({
  page,
}, testInfo) => {
  const fixture = environmentLanguageFixture();
  fixture.environment.runtime[0] = {
    ...fixture.environment.runtime[0],
    observed: "3.13.16",
    expected: ">=3.13.16,<3.14",
  };
  fixture.environment.runtime.push({
    id: "human-identity",
    label: "Original identity signal",
    scope: "gateway",
    status: "unverified",
    observed: "Original identity value",
    expected: "Original recovery policy",
    detail: "Original identity diagnostic",
  });
  let reads = 0;
  const errors: string[] = [],
    writes: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals" && request.method() === "POST")
      return route.fulfill({ status: 202, json: {} });
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
          display_name: "Original 科研",
          role: "admin",
        },
      });
    if (path === "/api/v1/enterprise/environment") {
      reads++;
      return route.fulfill({ json: fixture.environment });
    }
    return route.fulfill({ json: [] });
  });
  await page.setViewportSize({ width: 320, height: 900 });
  await page.goto("/workspace/internal?view=environment");
  const title = page.getByRole("heading", { name: "Environment", exact: true });
  await expect(title).toBeVisible();
  const commands = page.getByRole("tablist", { name: "Environment management functions", exact: true });
  for (const name of ["Checks", "Installation", "Evidence"]) {
    const box = await commands.getByRole("tab", { name, exact: true }).boundingBox();
    if (!box) throw new Error("Visible environment command is missing");
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
  }
  await page.evaluate(() => document.fonts.ready);
  expect((await title.boundingBox())?.height).toBeLessThanOrEqual(44);
  const readiness = page.getByRole("region", { name: "Dependency readiness overview", exact: true });
  await expect(readiness.getByText("Application gateway", { exact: true }).locator("+ dd")).toHaveText(
    "Dependencies available",
  );
  async function assertReadinessTextFits() {
    const labels = await page.locator(".environment-readiness-grid :is(dt, dd)").evaluateAll((nodes) =>
      nodes.map((node) => {
        const bounds = node.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(node);
        return {
          left: bounds.left,
          right: bounds.right,
          lines: Array.from(range.getClientRects(), (rect) => ({ left: rect.left, right: rect.right })),
        };
      }),
    );
    for (const label of labels) {
      for (const line of label.lines) {
        expect(line.left).toBeGreaterThanOrEqual(label.left - 1);
        expect(line.right).toBeLessThanOrEqual(label.right + 1);
      }
    }
  }
  await assertReadinessTextFits();
  const table = page.getByRole("table", { name: "Gateway dependency versions", exact: true });
  await expect(table).toBeVisible();
  await expect(table).toContainText("Original identity diagnostic");
  await expect(table).toContainText("Not verified");
  await selectInterfaceLanguage(page, "zh-CN");
  await assertReadinessTextFits();
  await expect(page.getByRole("heading", { name: "环境管理", exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "网关依赖版本", exact: true })).toContainText(
    "Original recovery policy",
  );
  expect(reads).toBe(1);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  expect(
    (await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("environment-compact-zh-320.png"), animations: "disabled" });
});

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
  await page.getByRole("tab", { name: "Installation", exact: true }).click();
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
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  const snapshot = page.locator(".platform-snapshot");
  await expect(snapshot).toBeVisible();
  const snapshotBounds = await snapshot.evaluate((node) => ({
    width: node.clientWidth,
    content: node.scrollWidth,
    whiteSpace: getComputedStyle(node).whiteSpace,
  }));
  expect(snapshotBounds.content).toBeLessThanOrEqual(snapshotBounds.width + 1);
  expect(snapshotBounds.whiteSpace).toBe("normal");
  const queueCount = page.locator(".platform-queue-metrics > div").first();
  await expect(queueCount).toContainText("Not observed");
  await expect(page.locator(".platform-queue-metrics > div").nth(3)).toContainText("0");
  await audit("unobserved-queues-en");
  await page.getByRole("tab", { name: "Installation", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Installation plan prepared, not executed", exact: true }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Python dependencies", exact: true }).check();
  await page.getByRole("button", { name: "Prepare installation plan", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("原始计划错误 — controlled browser fixture");
  await expect(page.getByRole("alert")).toHaveClass(/form-status-error/);
  await expect(page.getByRole("region", { name: "Prepared installation plan", exact: true })).toHaveCount(0);
  await audit("plan-error-en");
  expect(plans).toBe(2);
  expect(environmentReads).toBe(1);
  expect(platformReads).toBe(1);
  expect(writes).toEqual([]);
});
