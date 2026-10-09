import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { eventId, regulatoryEvent, regulatoryResult } from "../src/test/fixtures/regulatoryResearch";
import { selectInterfaceLanguage } from "./interface-language";

test("[regulatory-language] English-first controls retain drafts, comparison and original fields", async ({
  page,
}, testInfo) => {
  let reads = 0;
  const writes: string[] = [];
  const errors: string[] = [];
  const detail = {
    ...regulatoryEvent,
    title: "CONTROLLED FIXTURE · 原始监管决定 EGFR",
    details: { first: "原始 source", second: 0, third: false, fourth: "FOURTH_RAW_FIELD" },
  };
  page.on("pageerror", (error) => errors.push(error.message));
  // Browser-only response fixtures are neither ingestion input nor scientific evidence.
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
          id: "controlled-regulatory-user",
          tenant_id: "controlled-regulatory-tenant",
          email: "regulatory-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/regulatory-event-timeline") {
      reads++;
      return route.fulfill({ json: { ...regulatoryResult, items: [detail], total: 1 } });
    }
    if (path === `/api/v1/regulatory-event-timeline/${eventId}`) {
      reads++;
      return route.fulfill({ json: detail });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/workspace/research?view=regulatory&q=EGFR");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("table", { name: "Regulatory events", exact: true })).toContainText(detail.title);
  await page.getByText("More regulatory and safety filters", { exact: true }).click();
  await page
    .getByRole("group", { name: "Decision date", exact: true })
    .getByLabel("From", { exact: true })
    .fill("2026-01-01");
  await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交监管草稿");
  const originalUrl = page.url(),
    originalReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(originalUrl);
  await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交监管草稿");
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  expect(reads).toBe(originalReads);
  await page.getByRole("button", { name: `${detail.title}${detail.event_identifier}`, exact: true }).click();
  const drawer = page.getByRole("dialog", { name: detail.title, exact: true });
  await drawer.getByText("完整补充信息", { exact: true }).click();
  await expect(drawer.locator("pre")).toHaveText(JSON.stringify(detail.details, null, 2));
  await drawer.getByRole("button", { name: "关闭监管事件详情", exact: true }).click();
  await page.getByRole("checkbox", { name: `选择对比 ${detail.title}`, exact: true }).click();
  await expect(page.getByRole("table", { name: "监管事件对比", exact: true })).toContainText(detail.event_identifier);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("table", { name: "监管事件对比", exact: true })).toContainText(detail.event_identifier);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("regulatory-source-preserving-zh.png"), animations: "disabled" });
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
