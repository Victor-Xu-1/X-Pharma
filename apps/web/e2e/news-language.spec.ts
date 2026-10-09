import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { newsResult } from "../src/test/fixtures/newsResearch";
import { selectInterfaceLanguage } from "./interface-language";

const eventId = "550e8400-e29b-41d4-a716-446655440090";
const detail = {
  ...newsResult.items[0],
  id: eventId,
  details: { first: "原始 source", second: 0, third: false, fourth: "literal", fifth: "FIFTH_RAW_FIELD" },
};

test("[news-language] fresh English, retained drafts and complete detail fields", async ({ page }, testInfo) => {
  let reads = 0;
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Explicit browser-only responses, never a source, ingestion input or scientific acceptance.
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
          id: "controlled-news-user",
          tenant_id: "controlled-news-tenant",
          email: "news-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/news-events") {
      reads++;
      return route.fulfill({ json: { ...newsResult, items: [detail], total: 1 } });
    }
    if (path === `/api/v1/news-events/${eventId}`) {
      reads++;
      return route.fulfill({ json: detail });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=news&q=EGFR");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: "Research updates", exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Research updates", exact: true })).toContainText(detail.title);
  await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交的检索草稿");
  await page.getByText("More filters", { exact: true }).click();
  await page.getByLabel("Published from", { exact: true }).fill("2026-01-01");
  const appliedUrl = page.url(),
    originalReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(appliedUrl);
  await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交的检索草稿");
  await expect(page.getByLabel("发布起始", { exact: true })).toHaveValue("2026-01-01");
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  expect(reads).toBe(originalReads);
  await page.getByRole("button", { name: `打开新闻事件详情：${detail.title}`, exact: true }).click();
  const drawer = page.getByRole("dialog", { name: detail.title, exact: true });
  await expect(drawer).toBeVisible();
  const fields = drawer.locator(".knowledge-value-fields").first();
  expect(await fields.evaluate((node) => getComputedStyle(node).display)).toBe("grid");
  await drawer.getByText("完整补充信息", { exact: true }).click();
  await expect(drawer.locator("pre")).toHaveText(JSON.stringify(detail.details, null, 2));
  await drawer.getByRole("button", { name: "关闭新闻事件详情", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("table", { name: "新闻与会议结果", exact: true })).toContainText(detail.title);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("news-source-preserving-zh.png"), animations: "disabled" });
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);

  await selectInterfaceLanguage(page, "en");
  await page.getByRole("button", { name: "Statistics", exact: true }).click();
  const chart = page.locator(".landscape-bar-chart").first();
  async function hoverRecordBar() {
    await chart.scrollIntoViewIfNeeded();
    await expect(chart.locator("svg")).toBeVisible();
    const bar = await chart.locator("svg path").evaluateAll((nodes) =>
      nodes
        .map((node) => {
          const rect = node.getBoundingClientRect();
          return { fill: node.getAttribute("fill"), x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        })
        .find(
          (node) =>
            node.fill &&
            !["none", "transparent"].includes(node.fill) &&
            node.width > 20 &&
            node.height > 8 &&
            node.height < 40,
        ),
    );
    if (!bar) throw new Error("No visible record bar in the current SVG");
    await page.mouse.move(bar.x + bar.width / 2, bar.y + bar.height / 2);
  }
  await hoverRecordBar();
  await expect(page.getByText("1 updates", { exact: false })).toBeVisible();
  await selectInterfaceLanguage(page, "zh-CN");
  await hoverRecordBar();
  await expect(page.getByText("1 条动态", { exact: false })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("news-domain-count-unit-zh.png"), animations: "disabled" });
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
