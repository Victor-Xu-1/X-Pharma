import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installCommercialRecordFixture } from "./commercial-record-fixture";
import { selectInterfaceLanguage } from "./interface-language";

const inspections = [
  { key: "subscription", tab: "Contracts & quota", name: "ORIGINAL_SUBSCRIPTION", value: "ORIGINAL_ENTITLEMENT" },
  { key: "client", tab: "Clients", name: "原始 Agent <source>", value: "Original inactive subject <source>" },
  { key: "account", tab: "Billing", name: "ORIGINAL_ACCOUNT", value: "controlled-account" },
  { key: "delivery", tab: "Billing", name: "controlled-delivery-event", value: "Original provider detail <source>" },
  { key: "dispute", tab: "Disputes", name: "ORIGINAL_DISPUTE", value: "Original resolution <source>" },
  { key: "export", tab: "Exports", name: "controlled-export", value: "Original license <source>" },
  { key: "risk", tab: "Risk events", name: "controlled-risk", value: "Original review <source>" },
  { key: "hold", tab: "Data lifecycle", name: "ORIGINAL_MATTER", value: "Original release <source>" },
  { key: "audit", tab: "Data lifecycle", name: "controlled-lifecycle-event", value: "ORIGINAL_OPERATION_KEY" },
  { key: "source", tab: "Data lifecycle", name: "controlled-source-asset", value: "controlled-source" },
  { key: "withdrawn", tab: "Data lifecycle", name: "controlled-deleted-asset", value: "original/deleted <source>.md" },
  { key: "purge", tab: "Data lifecycle", name: "controlled-export", value: "Original license <source>" },
] as const;
test("[commercial-records] inspects returned metadata without an API write and retains each open dialog when language changes", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installCommercialRecordFixture(page);
  const languagePage = await context.newPage();
  await installCommercialRecordFixture(languagePage);
  await languagePage.goto("/workspace/internal?view=commercial");
  await page.goto("/workspace/internal?view=commercial");
  for (const item of inspections) {
    await selectInterfaceLanguage(languagePage, "en");
    await page.getByRole("tab", { name: item.tab, exact: true }).click();
    const summary = page.getByRole("button", { name: "View record details for " + item.name, exact: true });
    await expect(summary).toHaveJSProperty("tagName", "BUTTON");
    await summary.press("Enter");
    const row = summary.locator("..").locator("..");
    const rowBounds = await row.boundingBox();
    if (!rowBounds) throw new Error("Record summary row is missing");
    expect(rowBounds.height).toBeLessThanOrEqual(160);
    const region = page.getByRole("dialog", { name: "Record details for " + item.name, exact: true });
    await expect(region.getByText(item.value, { exact: true })).toBeVisible();
    const reads = state.reads;
    await selectInterfaceLanguage(languagePage, "zh-CN");
    const details = page.getByRole("dialog", { name: item.name + " 的记录详情", exact: true });
    await expect(details.getByText(item.value, { exact: true })).toBeVisible();
    expect(state.reads).toBe(reads);
    const bounds = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(
      (
        await new AxeBuilder({ page })
          .include(".commercial-record-panel")
          .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    if (["subscription", "delivery", "export", "source"].includes(item.key)) {
      await details.evaluate((node) => {
        node.scrollTop = 0;
      });
      await page.screenshot({
        path: testInfo.outputPath("commercial-record-" + item.key + "-zh.png"),
        animations: "disabled",
      });
    }
    expect(state.writes).toEqual([]);
    expect(base.state.writes).toEqual([]);
    expect(base.base.writes).toEqual([]);
    expect(base.base.errors).toEqual([]);
    await details.press("Escape");
    await expect(details).toHaveCount(0);
    await expect(page.getByRole("button", { name: "查看 " + item.name + " 的记录详情", exact: true })).toBeFocused();
  }
  await languagePage.close();
});
