import { expect, test } from "@playwright/test";
import { installDealFixture } from "./deal-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[table-preference-intent] a delayed reset preserves a newer sort, selection and bilingual draft", async ({
  page,
}, testInfo) => {
  const { state, deal } = await installDealFixture(page);
  const writes: unknown[] = [];
  let release = () => {};
  let completed = false;
  let persisted = false;
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/workspace/table-preferences/deals", async (route) => {
    const writing = route.request().method() === "PUT";
    if (writing) {
      writes.push(route.request().postDataJSON());
      await delayed;
      persisted = true;
    }
    await route.fulfill({
      json: {
        preference_key: "deals",
        schema_version: 1,
        column_order: [],
        column_visibility: {},
        density: persisted ? "comfortable" : "compact",
        version: persisted ? 2 : 1,
        persisted: true,
        updated_at: null,
      },
    });
    if (writing) completed = true;
  });
  try {
    await page.goto("/workspace/research?view=deals&q=VX-101&sort=name%3Adesc");
    const table = page.getByRole("table", { name: "Deal results", exact: true });
    await expect(page.getByRole("button", { name: "Compact", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("checkbox", { name: `Select Compare ${deal.name}`, exact: true }).check();
    await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交研究草稿");
    await page.locator(".table-view-reset").click();
    await expect.poll(() => writes.length).toBe(1);
    await table.locator("thead button").first().click();
    await page.waitForURL((url) => url.searchParams.get("sort") === "name:asc");
    const intendedURL = page.url();
    await selectInterfaceLanguage(page, "zh-CN");
    release();
    await expect.poll(() => completed).toBe(true);
    await expect(page.locator(".table-preference-sync")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "标准", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(intendedURL);
    await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交研究草稿");
    await expect(page.getByRole("checkbox", { name: `取消选择对比 ${deal.name}`, exact: true })).toBeChecked();
    await expect(page.getByRole("table", { name: "交易结果", exact: true })).toContainText(deal.name);
    await page
      .locator(".virtual-table-shell")
      .screenshot({ path: testInfo.outputPath("table-intent-zh.png"), animations: "disabled" });
    const reads = state.reads;
    await selectInterfaceLanguage(page, "en");
    await expect(page).toHaveURL(intendedURL);
    expect(state.reads).toBe(reads);
    expect(writes).toEqual([
      {
        column_order: [],
        column_visibility: {},
        density: "comfortable",
        expected_version: 1,
        schema_version: 1,
      },
    ]);
    await expect(page.getByRole("textbox", { name: "Keyword", exact: true })).toHaveValue("未提交研究草稿");
    await page
      .locator(".virtual-table-shell")
      .screenshot({ path: testInfo.outputPath("table-intent-en.png"), animations: "disabled" });
    expect(state.errors).toEqual([]);
    expect(state.writes).toEqual([]);
  } finally {
    release();
  }
});
