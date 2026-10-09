import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installDealFixture } from "./deal-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[deal-language] English-first filters retain selection, drafts and nested source terms across language changes", async ({
  page,
}, testInfo) => {
  const { state, deal, terms } = await installDealFixture(page);
  await page.goto("/workspace/research?view=deals&q=VX-101");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const table = page.getByRole("table", { name: "Deal results", exact: true });
  await expect(table).toContainText("USD 0.000123456");
  await expect(table).toContainText("USD 25,123,456.75");
  await page.getByRole("checkbox", { name: `Select Compare ${deal.name}`, exact: true }).check();
  await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交交易草稿");
  await page.getByText("More deal conditions", { exact: true }).click();
  await page
    .getByRole("group", { name: "Initial disclosure", exact: true })
    .getByLabel("From", { exact: true })
    .fill("2026-01-01");
  const url = page.url(),
    before = state.reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(url);
  expect(state.reads).toBe(before);
  await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交交易草稿");
  await expect(page.getByRole("checkbox", { name: `取消选择对比 ${deal.name}`, exact: true })).toBeChecked();
  await expect(
    page.getByRole("group", { name: "初始披露", exact: true }).getByLabel("起", { exact: true }),
  ).toHaveValue("2026-01-01");
  await page
    .getByRole("table", { name: "交易结果", exact: true })
    .getByRole("button", { name: /^CONTROLLED FIXTURE/ })
    .first()
    .click();
  await expect(page.getByRole("heading", { name: deal.name, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "条款与来源", exact: true }).click();
  await page.getByText("完整补充信息", { exact: true }).click();
  await expect(page.locator(".source-metadata pre")).toHaveText(JSON.stringify(terms, null, 2));
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("tab", { name: "条款与来源", exact: true })).toHaveAttribute("aria-selected", "true");
  await selectInterfaceLanguage(page, "en");
  await page.getByText("Complete source metadata", { exact: true }).click();
  await expect(page.locator(".source-metadata pre")).toHaveText(JSON.stringify(terms, null, 2));
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("deal-source-preserving-en.png"), animations: "disabled" });
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});

test("[deal-language] explicit currency validation and failed organization suggestions retain drafts and current language", async ({
  page,
}, testInfo) => {
  const { state } = await installDealFixture(page);
  await page.goto("/workspace/research?view=deals&q=VX-101&currency=USD&sort=name%3Aasc&sort=upfront_amount%3Adesc");
  await page.getByRole("table", { name: "Deal results", exact: true }).waitFor();
  const url = page.url(),
    before = state.reads;
  await page.getByLabel("Currency", { exact: true }).selectOption("");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Choose a currency to sort by deal amount");
  expect(page.url()).toBe(url);
  expect(state.reads).toBe(before);
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("alert")).toHaveText("按交易金额排序时必须选择币种");
  await expect(page.getByLabel("币种", { exact: true })).toHaveValue("");
  await selectInterfaceLanguage(page, "en");
  await page
    .getByRole("group", { name: "Upfront amount", exact: true })
    .getByLabel("Minimum", { exact: true })
    .fill("0");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Choose a currency to search by deal amount");
  expect(state.reads).toBe(before);
  await page.getByLabel("Currency", { exact: true }).selectOption("USD");
  await page
    .getByRole("group", { name: "Upfront amount", exact: true })
    .getByLabel("Minimum", { exact: true })
    .fill("0.000123456");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.waitForURL((location) => location.searchParams.get("upfront_amount_min") === "0.000123456");
  await expect.poll(() => state.lastUpfrontMinimum).toBe("0.000123456");
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByText("Participants and linked assets", { exact: true }).click();
  const party = page.getByRole("combobox", { name: "Participating organization", exact: true });
  await party.fill("Acme");
  await expect(page.getByRole("alert")).toHaveText("Organization search failed: RAW_ORGANIZATION_FAILURE");
  // The existing application policy makes the initial attempt plus two bounded
  // retries for a 503; switching language must not add another request.
  expect(state.organizationReads).toBe(3);
  await expect(page.getByText("No matching organizations", { exact: true })).toHaveCount(0);
  await selectInterfaceLanguage(page, "zh-CN");
  // Changing the interface control deliberately closes the focused suggestion popup.
  await page.getByRole("combobox", { name: "参与机构", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("机构查询失败：RAW_ORGANIZATION_FAILURE");
  expect(state.organizationReads).toBe(3);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  state.organizationStatus = 200;
  await page.getByRole("button", { name: "重试机构查询", exact: true }).click();
  await expect(page.getByText("未找到匹配机构", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "参与机构", exact: true })).toHaveValue("Acme");
  await page.screenshot({ path: testInfo.outputPath("deal-recovered-organization-zh.png"), animations: "disabled" });
  expect(state.organizationReads).toBe(4);
  const validReads = state.reads;
  await page.goto("/workspace/research?view=deals&upfront_amount_min=0");
  await expect(page.getByRole("alert")).toContainText("按交易金额查询时必须选择币种");
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("alert")).toContainText("Choose a currency to search by deal amount");
  await expect(page.getByRole("table", { name: "Deal results", exact: true })).toHaveCount(0);
  expect(state.reads).toBe(validReads);
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});
