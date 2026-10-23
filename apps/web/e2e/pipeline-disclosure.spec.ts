import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { PipelineSearchResult } from "../src/lib/generated";
import { expectCompactSecondaryFilters } from "./fixtures/compact-secondary-filters";
import { readViewportOverflow } from "./fixtures/viewport-overflow";
import { selectInterfaceLanguage } from "./interface-language";

test("[pipeline-disclosure] retains unsent dates and false-valued signal filters through clear and language changes", async ({
  page,
}, testInfo) => {
  const response: PipelineSearchResult = {
    items: [],
    total: 0,
    offset: 0,
    limit: 20,
    as_of: "2026-10-11T00:00:00Z",
    query_schema_version: "pharma.pipeline.search.v13",
    sort_by: "status_date",
    sort_direction: "desc",
    facets: {},
    landscape: {
      total_programs: 0,
      distinct_drugs: 0,
      distinct_targets: 0,
      distinct_diseases: 0,
      distinct_organizations: 0,
      limit: 8,
      stage_scope: "overall",
      target_aggregation: "all",
    },
  };
  let reads = 0;
  const writes: string[] = [],
    errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Controlled empty responses verify UI state only, never source coverage or scientific records.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-pipeline-user",
          tenant_id: "controlled-pipeline-tenant",
          email: "pipeline@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/pipelines") {
      reads++;
      return route.fulfill({ json: response });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/workspace/research?view=pipeline");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator(".pipeline-section .domain-results")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("pipeline-default-en.png"), animations: "disabled" });
  const exact = page.locator(".pipeline-entity-disclosure");
  await expect(exact).not.toHaveAttribute("open", "");
  await expect(exact.getByRole("combobox")).toHaveCount(0);
  await exact.locator(":scope > summary").click();
  const targetDraft = exact.getByRole("combobox", { name: "Target filter", exact: true });
  await targetDraft.fill("x");
  await exact.locator(":scope > summary").click();
  await expect(targetDraft).toBeHidden();
  const advanced = page.locator(".pipeline-advanced-filters").first();
  const signals = page.locator(".pipeline-advanced-filters").nth(1);
  await expect(advanced).toHaveClass(/secondary-filter-panel/);
  await expect(signals).toHaveClass(/secondary-filter-panel/);
  await expect(advanced).not.toHaveAttribute("open", "");
  await expect.poll(() => reads).toBe(1);
  await selectInterfaceLanguage(page, "zh-CN");
  await exact.locator(":scope > summary").click();
  await expect(exact.getByRole("combobox", { name: "靶点筛选", exact: true })).toHaveValue("x");
  await exact.locator(":scope > summary").click();
  await expect(advanced.locator(":scope > summary > span")).toHaveText("机构、区域阶段、权益与里程碑");
  await expect(signals.locator(":scope > summary > span")).toHaveText("临床结果与交易信号");
  await selectInterfaceLanguage(page, "en");
  await expect(exact).not.toHaveAttribute("open", "");
  await expect(advanced.locator(":scope > summary > span")).toHaveText(
    "Organizations, regional phases, rights and milestones",
  );
  await expect(signals.locator(":scope > summary > span")).toHaveText("Clinical results and deal signals");
  const originalReads = reads,
    originalUrl = page.url();
  await advanced.locator(":scope > summary").click();
  const start = advanced
    .getByRole("group", { name: "Global phase start dates", exact: true })
    .getByLabel("From", { exact: true });
  await start.fill("2026-01-02");
  await selectInterfaceLanguage(page, "zh-CN");
  const chineseStart = advanced
    .getByRole("group", { name: "全球阶段起始日期", exact: true })
    .getByLabel("起", { exact: true });
  await expect(chineseStart).toHaveValue("2026-01-02");
  await chineseStart.fill("");
  await expect(advanced).toHaveAttribute("open", "");
  await expect(advanced).toHaveAttribute("data-active-count", "0");
  await expect(advanced.locator(":scope > .pipeline-advanced-grid")).toHaveCount(1);
  await signals.locator(":scope > summary").click();
  const presence = signals.getByRole("combobox", { name: "是否存在交易记录", exact: true });
  await presence.selectOption("false");
  await expect(signals).toHaveAttribute("data-active-count", "1");
  await expect(signals.getByRole("combobox", { name: "交易币种", exact: true })).toBeDisabled();
  await selectInterfaceLanguage(page, "en");
  const englishPresence = signals.getByRole("combobox", { name: "Deal records available", exact: true });
  await expect(englishPresence).toHaveValue("false");
  await englishPresence.selectOption("");
  await expect(signals).toHaveAttribute("open", "");
  await expect(signals).toHaveAttribute("data-active-count", "0");
  await expect(signals.getByRole("combobox", { name: "Deal currency", exact: true })).toBeEnabled();
  await expectCompactSecondaryFilters(page);
  expect(reads).toBe(originalReads);
  expect(page.url()).toBe(originalUrl);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  const overflow = await readViewportOverflow(page);
  if (overflow.document > overflow.viewport) {
    await testInfo.attach("viewport-overflow", {
      body: JSON.stringify(overflow, null, 2),
      contentType: "application/json",
    });
    console.log(JSON.stringify(overflow));
  }
  expect(overflow.document).toBeLessThanOrEqual(overflow.viewport);
  await page.screenshot({ path: testInfo.outputPath("controlled-pipeline-disclosure-en.png"), animations: "disabled" });
});
