import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installChemistryLocaleFixture } from "./chemistry-locale-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[chemistry-locale-query] preserves a pending source query, localized rejection and explicit recovery", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installChemistryLocaleFixture(page);
  await page.goto("/workspace/research?view=chemistry");
  await page.getByRole("tab", { name: "Advanced input", exact: true }).click();
  await page.getByRole("textbox", { name: "SMILES", exact: true }).fill("invalid-structure");
  state.holdRead = true;
  state.invalid = true;
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("button", { name: "Searching", exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installChemistryLocaleFixture(second);
  await second.goto("/workspace/research?view=chemistry");
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(page.getByRole("textbox", { name: "SMILES", exact: true })).toHaveValue("invalid-structure");
  expect(state.reads).toEqual([{ mode: "exact", query: "invalid-structure", threshold: 0.7, limit: 20 }]);
  state.releaseRead?.();
  await expect(page.getByRole("alert")).toContainText("无法识别该 SMILES");
  await expect(page.getByRole("alert")).not.toContainText("PRIVATE_PARSER_DETAIL");
  await selectInterfaceLanguage(second, "en");
  await expect(page.getByRole("alert")).toContainText("This SMILES could not be parsed");
  await expect(page.getByText("No structure query has been run", { exact: true })).toHaveCount(0);
  expect(state.reads).toHaveLength(1);
  await page.screenshot({ path: testInfo.outputPath("chemistry-invalid-en.png"), animations: "disabled" });
  state.holdRead = false;
  state.invalid = false;
  await page.getByRole("textbox", { name: "SMILES", exact: true }).fill("CCO");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("No matching structures", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save structure search", exact: true })).toBeEnabled();
  expect(
    (
      await new AxeBuilder({ page })
        .include(".chemistry-workbench")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  await second.close();
});
test("[chemistry-locale-save] keeps the original saved title and captured source intent across pending failure and language changes", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installChemistryLocaleFixture(page);
  await page.goto("/workspace/research?view=chemistry");
  await page.getByRole("tab", { name: "Advanced input", exact: true }).click();
  await page.getByRole("textbox", { name: "SMILES", exact: true }).fill("C[C@H](O)C(=O)O");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("button", { name: "Save structure search", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Save structure search", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("textbox", { name: "Name", exact: true }).fill("Original source title <preserve>");
  state.holdSave = true;
  state.rejectSave = true;
  await dialog.getByRole("button", { name: "Save search", exact: true }).click();
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installChemistryLocaleFixture(second);
  await second.goto("/workspace/research?view=chemistry");
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(dialog.getByRole("textbox", { name: "名称", exact: true })).toHaveValue(
    "Original source title <preserve>",
  );
  await expect(dialog.getByRole("button", { name: "关闭", exact: true })).toBeDisabled();
  expect(state.saves).toHaveLength(1);
  expect(state.saves[0]).toMatchObject({
    name: "Original source title <preserve>",
    query_type: "chemistry_search",
    query: { mode: "exact", query: "C[C@H](O)C(=O)O", threshold: 0.7, limit: 20 },
    visibility: "private",
  });
  state.releaseSave?.();
  await expect(dialog.getByRole("alert")).toContainText("RAW_CONTROLLED_SAVE_FAILURE");
  await expect(dialog.getByRole("textbox", { name: "名称", exact: true })).toBeEnabled();
  await selectInterfaceLanguage(second, "en");
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toHaveValue(
    "Original source title <preserve>",
  );
  expect(state.saves).toHaveLength(1);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".workspace-modal")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("chemistry-save-failed-en.png"), animations: "disabled" });
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  await second.close();
});
