import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installEnterpriseLanguageFixture } from "./enterprise-language-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[enterprise-language] retains a captured group request across language changes, blocks conflicting controls and keeps a rejected draft", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installEnterpriseLanguageFixture(page);
  await page.goto("/workspace/internal?view=enterprise");
  await page.getByRole("tab", { name: "Groups", exact: true }).click();
  const opener = page.getByRole("button", { name: "New group", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "New group", exact: true });
  await dialog.getByRole("textbox", { name: "Group name", exact: true }).fill("Original group <source>");
  await dialog.getByRole("textbox", { name: "Description", exact: true }).fill("Original description <source>");
  state.hold = true;
  state.fail = true;
  await dialog.getByRole("button", { name: "Create group", exact: true }).click();
  await expect(dialog.getByRole("textbox", { name: "Group name", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Close", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Users & roles", exact: true })).toBeDisabled();
  await dialog.press("Escape");
  await expect(dialog).toBeVisible();
  const second = await context.newPage();
  await installEnterpriseLanguageFixture(second);
  await second.goto("/workspace/internal?view=enterprise");
  const reads = state.reads;
  await selectInterfaceLanguage(second, "zh-CN");
  const chinese = page.getByRole("dialog", { name: "新建用户组", exact: true });
  await expect(chinese.getByRole("textbox", { name: "用户组名称", exact: true })).toHaveValue(
    "Original group <source>",
  );
  expect(state.reads).toBe(reads);
  expect(state.writes).toEqual([{ name: "Original group <source>", description: "Original description <source>" }]);
  state.release?.();
  await expect(chinese.getByRole("alert")).toContainText("RAW_CONTROLLED_GROUP_FAILURE");
  await expect(chinese.getByRole("textbox", { name: "用户组名称", exact: true })).toBeEnabled();
  expect(
    (
      await new AxeBuilder({ page })
        .include(".enterprise-modal-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const bounds = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
  await page.screenshot({ path: testInfo.outputPath("enterprise-group-failed-zh.png"), animations: "disabled" });
  await chinese.press("Escape");
  await expect(chinese).toHaveCount(0);
  await expect(page.getByRole("button", { name: "新建用户组", exact: true })).toBeFocused();
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  expect(state.writes).toHaveLength(1);
  await second.close();
});
