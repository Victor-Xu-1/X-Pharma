import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { observation, searchResult } from "../src/test/fixtures/epidemiologyResearch";
import { selectInterfaceLanguage } from "./interface-language";

test("[epidemiology-language] English-first controls retain drafts, comparable data and saved choice", async ({
  page,
}, testInfo) => {
  let reads = 0;
  const errors: string[] = [],
    writes: string[] = [];
  const record = {
    ...observation,
    value: 0,
    lower_bound: 0,
    upper_bound: null,
    sample_size: 0,
    methodology: "原始 SOURCE_METHOD",
  };
  page.on("pageerror", (error) => errors.push(error.message));
  // Explicit browser-only responses; not a source, ingestion input or scientific evidence.
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
          id: "controlled-epidemiology-user",
          tenant_id: "controlled-epidemiology-tenant",
          email: "epidemiology-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/epidemiology-observations") {
      reads++;
      return route.fulfill({ json: { ...searchResult, items: [record], total: 1 } });
    }
    if (path.startsWith("/api/v1/epidemiology-trends/")) {
      reads++;
      return route.fulfill({
        json: {
          disease: record.disease_entity,
          anchor_observation_id: record.id,
          items: [record],
          total: 1,
          truncated: false,
          as_of: searchResult.as_of,
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/workspace/research?view=epidemiology&q=NSCLC");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const table = page.getByRole("table", { name: "Epidemiology observations", exact: true });
  await expect(table).toContainText(record.methodology);
  await expect(table).toContainText(record.patient_population.name);
  await page.getByText("More filters", { exact: true }).click();
  await page.getByLabel("Observed from", { exact: true }).fill("2025-01-01");
  await page.getByRole("textbox", { name: "Source or method", exact: true }).fill("未提交原始草稿");
  const url = page.url(),
    originalReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(url);
  await expect(page.getByRole("textbox", { name: "来源或方法", exact: true })).toHaveValue("未提交原始草稿");
  await expect(page.getByLabel("观察期起", { exact: true })).toHaveValue("2025-01-01");
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  expect(reads).toBe(originalReads);
  await page.getByRole("button", { name: `查看 ${record.disease_entity.name} 同口径趋势`, exact: true }).click();
  await expect(page.getByRole("table", { name: "同口径趋势数据", exact: true })).toContainText(record.methodology);
  const scroll = page.getByRole("region", { name: "同口径趋势表滚动区域", exact: true });
  await expect(scroll).toHaveAttribute("tabindex", "0");
  await scroll.scrollIntoViewIfNeeded();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("epidemiology-original-values-zh.png"), animations: "disabled" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("table", { name: "流行病学结果", exact: true })).toContainText(record.methodology);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
