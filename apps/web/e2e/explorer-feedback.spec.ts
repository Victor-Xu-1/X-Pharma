import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installGovernanceFixture } from "./governance-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[explorer-feedback] keeps 320px search and save commands at a standard single-line height", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 320, height: 844 });
  const base = await installGovernanceFixture(page);
  await page.route("**/api/v1/entities?**", (route) =>
    route.fulfill({
      json: { items: [], total: 0, offset: 0, limit: 100, facets: {}, warnings: [], applied_filters: [] },
    }),
  );
  await page.goto("/workspace/research?view=explorer&q=EGFR&review=verified");
  for (const locale of ["en", "zh-CN"] as const) {
    await selectInterfaceLanguage(page, locale);
    const row = page.locator(".intelligence-query-panel > .query-row").first();
    const buttons = row.locator(":scope > button");
    await expect(buttons).toHaveCount(2);
    for (const button of await buttons.all()) {
      const box = await button.boundingBox();
      expect(box).not.toBeNull();
      expect(box?.height).toBeLessThanOrEqual(44);
      expect(box?.x).toBeGreaterThanOrEqual(0);
      expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(320);
      expect((await button.locator("svg").boundingBox())?.width).toBeGreaterThanOrEqual(14);
    }
    await page.screenshot({ path: testInfo.outputPath(`commands-${locale}-320.png`), animations: "disabled" });
  }
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
});

test("[explorer-feedback] retains saved outcomes across languages without recreating the query or translating source reasons", async ({
  page,
}, testInfo) => {
  const base = await installGovernanceFixture(page);
  const state = { saves: 0, topics: 0, queries: 0, failMonitor: false };
  const reason = "Original <EGFR> {reason} 科研";
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET" && path === "/api/v1/entities") {
      state.queries++;
      return route.fulfill({
        json: { items: [], total: 0, offset: 0, limit: 100, facets: {}, warnings: [], applied_filters: [] },
      });
    }
    if (request.method() === "POST" && path === "/api/v1/monitoring/saved-searches") {
      state.saves++;
      expect(request.postDataJSON().name).toBe("Original saved query 科研");
      return route.fulfill({ json: { id: "controlled-saved-search", name: "Original saved query 科研" } });
    }
    if (request.method() === "POST" && path === "/api/v1/monitoring/topics") {
      state.topics++;
      expect(request.postDataJSON()).toEqual({
        name: "Original saved query 科研",
        saved_search_id: "controlled-saved-search",
      });
      return state.failMonitor
        ? route.fulfill({ status: 503, json: { detail: reason } })
        : route.fulfill({ json: { id: "controlled-monitoring-topic" } });
    }
    return route.fallback();
  });
  await page.goto("/workspace/research?view=explorer&q=EGFR&type=target&review=verified");
  await expect(page.getByRole("combobox", { name: "Interface language", exact: true })).toHaveValue("en");
  for (const outcome of ["saved", "monitored", "partial"] as const) {
    state.failMonitor = outcome === "partial";
    await selectInterfaceLanguage(page, "en");
    await page.getByRole("button", { name: "Save search", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Save current search", exact: true });
    await dialog.getByLabel("Name", { exact: true }).fill("Original saved query 科研");
    if (outcome === "saved")
      await dialog.getByRole("checkbox", { name: "Also subscribe to related data changes", exact: true }).uncheck();
    else await dialog.getByRole("checkbox", { name: "Also subscribe to related data changes", exact: true }).check();
    await dialog.getByRole("button", { name: "Save search", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const feedback = page.locator(".explorer-section > .inline-feedback[role=status]");
    const before = { ...state };
    for (const locale of ["en", "zh-CN"] as const) {
      await selectInterfaceLanguage(page, locale);
      const text =
        outcome === "partial"
          ? locale === "en"
            ? `Search saved, but monitoring was not enabled: ${reason}`
            : `检索已保存，但监控未启用：${reason}`
          : outcome === "monitored"
            ? locale === "en"
              ? "Search saved and monitoring enabled"
              : "基础查询检索已保存并启用监控"
            : locale === "en"
              ? "Search saved"
              : "基础查询检索已保存";
      await expect(feedback).toHaveText(text);
      expect(state).toEqual(before);
      await expect(page.locator("#intelligence-query")).toHaveValue("EGFR");
      expect(
        (
          await new AxeBuilder({ page })
            .include("main")
            .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      const geometry = await page.evaluate(() => ({
        viewport: innerWidth,
        document: document.documentElement.scrollWidth,
      }));
      expect(geometry.document).toBeLessThanOrEqual(geometry.viewport);
      await feedback.scrollIntoViewIfNeeded();
      const feedbackBox = await feedback.boundingBox();
      expect(feedbackBox).not.toBeNull();
      if (feedbackBox) {
        expect(feedbackBox.y).toBeGreaterThanOrEqual(0);
        expect(feedbackBox.y + feedbackBox.height).toBeLessThanOrEqual(page.viewportSize()?.height ?? 0);
      }
      await page.screenshot({ path: testInfo.outputPath(`${outcome}-${locale}.png`), animations: "disabled" });
    }
  }
  expect(state.saves).toBe(3);
  expect(state.topics).toBe(2);
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
});
