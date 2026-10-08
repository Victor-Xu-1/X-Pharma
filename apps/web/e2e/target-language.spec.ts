import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { targetLanguageFixture } from "./fixtures/target-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[target-language] preserves target narratives, complete counts, filters, registry identity and cached reads", async ({
  page,
}, testInfo) => {
  const fixture = targetLanguageFixture();
  let dossierReads = 0;
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Only controlled API fixtures. No real identity, facts, provider calls or server mutations.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    // The existing UI emits bounded performance telemetry; fulfill it locally too.
    // This is not a scientific/account write and never reaches a real service.
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
          id: "controlled-target-user",
          tenant_id: "controlled-target-tenant",
          email: "target-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === `/api/v1/entities/${fixture.entity.id}`) return route.fulfill({ json: fixture.entity });
    if (path === `/api/v1/targets/${fixture.entity.id}/dossier`) {
      dossierReads++;
      return route.fulfill({ json: fixture });
    }
    return route.fulfill({ json: [] });
  });
  async function audit(name: string) {
    expect(
      (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
    ).toEqual([]);
    const bounds = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false, animations: "disabled" });
  }
  await page.goto(`/workspace/research?view=target&entity=${fixture.entity.id}&section=overview`);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: "Function summary", exact: true })).toBeVisible();
  await expect(page.locator(".narrative-section p")).toHaveText(fixture.entity.description ?? "");
  await expect(page.getByText("1,200 related records; 50 currently shown", { exact: true })).toBeVisible();
  await expect(page.getByText("137 recruiting trials", { exact: true })).toBeVisible();
  await audit("target-overview-en");
  await page.getByRole("tab", { name: "Translational evidence", exact: true }).click();
  const filterLayout = await page.locator(".target-evidence-filters").evaluate((node) => {
    const style = getComputedStyle(node);
    const labels = [...node.querySelectorAll("label")].map((label) => {
      const bounds = label.getBoundingClientRect();
      return { y: bounds.y, bottom: bounds.bottom };
    });
    return {
      borderTop: style.borderTopStyle,
      borderLeft: style.borderLeftStyle,
      borderRight: style.borderRightStyle,
      labels,
    };
  });
  expect([filterLayout.borderTop, filterLayout.borderLeft, filterLayout.borderRight]).toEqual(["none", "none", "none"]);
  if ((page.viewportSize()?.width ?? 1440) < 500)
    expect(filterLayout.labels[1].y).toBeGreaterThanOrEqual(filterLayout.labels[0].bottom);
  await page.getByRole("combobox", { name: "Evidence type", exact: true }).selectOption("expression");
  await expect(page.getByText("No evidence matches the current filters", { exact: true })).toBeVisible();
  const emptyUrl = page.url();
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("combobox", { name: "证据类型", exact: true })).toHaveValue("expression");
  await expect(page.getByText("当前筛选条件下无匹配证据", { exact: true })).toBeVisible();
  expect(page.url()).toBe(emptyUrl);
  await page.getByRole("combobox", { name: "证据类型", exact: true }).selectOption("genetic_association");
  await page.getByRole("combobox", { name: "证据方向", exact: true }).selectOption("supports");
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("combobox", { name: "Evidence direction", exact: true })).toHaveValue("supports");
  const evidence = page.getByRole("table", { name: "Target translational evidence", exact: true });
  await expect(evidence).toContainText(fixture.target_evidence[0].summary);
  await expect(evidence).toContainText("Supports the target hypothesis");
  await audit("target-evidence-en");
  await page.getByRole("tab", { name: "Relationship network", exact: true }).click();
  const relationships = page.getByRole("table", { name: "Target entity relationships", exact: true });
  await expect(relationships).toContainText("Registry sponsor");
  await expect(relationships).toContainText("原始登记申办方 — browser fixture");
  await audit("target-relationships-en");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("tab", { name: "关系网络", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("table", { name: "靶点实体关系", exact: true })).toContainText("登记申办方");
  expect(dossierReads).toBe(1);
  expect(writes).toEqual([]);
  await audit("target-relationships-zh");
});
