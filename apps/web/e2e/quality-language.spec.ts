import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { selectInterfaceLanguage } from "./interface-language";
import { installQualityFixture, qualityIssue } from "./quality-fixture";

test("[quality-language] preserves issue drafts, original metrics and one shared pending intent", async ({
  page,
}, testInfo) => {
  const { base, state } = await installQualityFixture(page);
  await page.goto("/workspace/internal?view=governance");
  await page.getByRole("tab", { name: "Data quality", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Data quality operations" })).toBeVisible();
  const owner = page.getByRole("combobox", { name: "Owner", exact: true });
  await expect(owner).toBeEnabled();
  await owner.selectOption("controlled-owner");
  const notes = page.getByRole("textbox", { name: "Action notes", exact: true });
  await notes.fill("Original A draft <source>");
  await page.getByRole("button", { name: /原始质量记录 B/ }).click();
  await expect(owner).toHaveValue("");
  await expect(notes).toHaveValue("");
  await page.getByRole("button", { name: /原始质量记录 A/ }).click();
  await expect(owner).toHaveValue("controlled-owner");
  await expect(notes).toHaveValue("Original A draft <source>");
  await page.getByRole("tab", { name: /^Fact review/ }).click();
  await page.getByRole("tab", { name: "Data quality", exact: true }).click();
  await expect(notes).toHaveValue("Original A draft <source>");
  await expect(owner).toHaveValue("controlled-owner");
  await page.getByText("Full issue record", { exact: true }).click();
  const beforeLanguage = state.reads;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "处置说明", exact: true })).toHaveValue("Original A draft <source>");
  await expect(page.getByText("完整事件记录", { exact: true }).locator("..")).toHaveAttribute("open", "");
  expect(state.reads).toBe(beforeLanguage);
  state.hold = true;
  await page.getByRole("button", { name: "分配", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "负责人", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: /^事实审核/ })).toBeDisabled();
  await selectInterfaceLanguage(page, "en");
  await expect(notes).toBeDisabled();
  await expect(owner).toHaveValue("controlled-owner");
  await expect(page.getByRole("button", { name: "Evaluate now", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "Issue status", exact: true })).toBeDisabled();
  await expect(page.getByRole("columnheader", { name: "原始新增指标" })).toBeVisible();
  expect(state.writes).toEqual([
    { action: "assign", expected_version: 1, owner_user_id: "controlled-owner", notes: "Original A draft <source>" },
  ]);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".quality-operations")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const bounds = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
  await page.screenshot({
    path: testInfo.outputPath("quality-pending-en.png"),
    fullPage: true,
    animations: "disabled",
  });
  state.release?.();
  await expect(notes).toHaveValue("");
  state.denied = true;
  await page.getByRole("button", { name: "Refresh quality issues", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_QUALITY_DENIAL");
  await expect(page.getByRole("heading", { name: qualityIssue.title })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Assign", exact: true })).toHaveCount(0);
  expect(base.writes).toEqual([]);
  expect(base.errors).toEqual([]);
});
