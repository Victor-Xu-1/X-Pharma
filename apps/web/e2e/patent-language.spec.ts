import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { PublicResearchCoverage } from "../src/lib/generated";
import { patentResult } from "../src/test/fixtures/patentsResearch";
import { expectCompactSecondaryFilters } from "./fixtures/compact-secondary-filters";
import { expectCompactTableToolbar, expectCompactWorkspaceHeading } from "./fixtures/compact-workspace-reading";
import { expectPublicResearchFormLayout } from "./fixtures/public-research-reading";
import { expectResearchReadingLayout } from "./fixtures/reading-layout";
import { installReadOnlyTablePreference } from "./fixtures/table-preferences";
import { selectInterfaceLanguage } from "./interface-language";

test("[patent-language] English-first filters keep drafts, selection and source publications across language changes", async ({
  page,
}, testInfo) => {
  let reads = 0;
  const writes: string[] = [],
    errors: string[] = [];
  const patent = {
    ...patentResult.items[0],
    id: "550e8400-e29b-41d4-a716-446655440021",
    title: "CONTROLLED FIXTURE · 原始专利标题",
  };
  page.on("pageerror", (error) => errors.push(error.message));
  // Isolated browser responses, never authoritative records or coverage evidence.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/public-research/coverage")
      return route.fulfill({
        json: {
          entity_counts: {},
          observed_at: "2026-10-11T00:00:00Z",
          public_source_names: [],
          scope_note: "CONTROLLED FIXTURE · Empty local coverage, not a scientific coverage claim",
        } satisfies PublicResearchCoverage,
      });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-patent-user",
          tenant_id: "controlled-patent-tenant",
          email: "patent-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/patent-families") {
      reads++;
      return route.fulfill({ json: { ...patentResult, items: [patent], total: 1 } });
    }
    if (path === `/api/v1/patent-families/${patent.id}`) {
      reads++;
      return route.fulfill({ json: patent });
    }
    return route.fulfill({ json: [] });
  });
  await installReadOnlyTablePreference(page, "patent-families");
  await page.goto("/workspace/research?view=patents&q=EGFR");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const results = page.getByRole("table", { name: "Patent family results", exact: true });
  await expect(results).toContainText(patent.title);
  await expectCompactTableToolbar(page, false);
  await expectCompactWorkspaceHeading(page);
  await expectCompactSecondaryFilters(page);
  const originalViewport = page.viewportSize();
  if (testInfo.project.name === "mobile-390" && originalViewport) {
    await page.setViewportSize({ width: 320, height: originalViewport.height });
    try {
      await expectCompactTableToolbar(page, false);
      await expectCompactWorkspaceHeading(page);
      await expectCompactSecondaryFilters(page);
      await page
        .locator(".virtual-table-shell")
        .screenshot({ path: testInfo.outputPath("compact-toolbar-320-en.png"), animations: "disabled" });
    } finally {
      await page.setViewportSize(originalViewport);
    }
  }
  await page.screenshot({ path: testInfo.outputPath("compact-reading-empty-en.png"), animations: "disabled" });
  await expect(page.getByLabel("Applicant", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Legal status", { exact: true })).toHaveValue("");
  await expect(results.getByText("Active", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: `Select Compare ${patent.family_identifier}`, exact: true }).check();
  await page.getByText("More patent conditions", { exact: true }).click();
  await page
    .getByRole("group", { name: "Priority dates", exact: true })
    .getByLabel("From", { exact: true })
    .fill("2021-02-03");
  await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交专利草稿");
  const originalUrl = page.url(),
    originalReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(originalUrl);
  expect(reads).toBe(originalReads);
  await expect(page.getByLabel("申请人", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("法律状态", { exact: true })).toHaveValue("");
  await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交专利草稿");
  await expect(
    page.getByRole("checkbox", { name: `取消选择对比 ${patent.family_identifier}`, exact: true }),
  ).toBeChecked();
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  await expectResearchReadingLayout(page, page.locator(".virtual-data-table"));
  await expectCompactWorkspaceHeading(page);
  await expectCompactTableToolbar(page, true);
  await expectCompactSecondaryFilters(page);
  await page.screenshot({ path: testInfo.outputPath("compact-reading-selected-zh.png"), animations: "disabled" });
  await expectPublicResearchFormLayout(page);
  await page.getByRole("button", { name: `打开专利族详情：${patent.family_identifier}`, exact: true }).click();
  await expect(page.getByRole("table", { name: "公开文本", exact: true })).toContainText("WO2022123456A1");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("heading", { name: patent.title, exact: true })).toBeVisible();
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("table", { name: "Publications", exact: true })).toContainText("WO2022123456A1");
  await page.getByRole("button", { name: "Back to patent families", exact: true }).click();
  await page.goto("/workspace/research?view=patents&priority_from=2021-02-03&expiration_to=2042-02-03");
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Clear", exact: true })).toBeEnabled();
  await expect(
    page.getByRole("group", { name: "Priority dates", exact: true }).getByLabel("From", { exact: true }),
  ).toHaveValue("2021-02-03");
  await expect(
    page.getByRole("group", { name: "Estimated expiration dates", exact: true }).getByLabel("To", { exact: true }),
  ).toHaveValue("2042-02-03");
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await expect(page.locator(".table-preference-error")).toHaveCount(0);
  await expect(page.locator(".table-density-control button").first()).toBeEnabled();
  await expectResearchReadingLayout(page, results);
  await expectPublicResearchFormLayout(page);
  await page.screenshot({ path: testInfo.outputPath("patent-source-preserving-en.png"), animations: "disabled" });
  expect(
    (
      await new AxeBuilder({ page })
        .include('[data-testid="public-research-panel"]')
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const viewport = page.locator(".virtual-table-viewport");
  await page
    .locator(".virtual-table-shell")
    .screenshot({ path: testInfo.outputPath("patent-readable-table-en.png"), animations: "disabled" });
  await viewport.evaluate((node) => {
    node.scrollLeft = node.scrollWidth - node.clientWidth;
  });
  await page
    .locator(".virtual-table-shell")
    .screenshot({ path: testInfo.outputPath("patent-readable-table-end-en.png"), animations: "disabled" });
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
