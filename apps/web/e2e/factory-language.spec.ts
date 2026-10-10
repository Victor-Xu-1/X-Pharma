import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { factoryAsset, factoryQuarantine, factorySource, installFactoryFixture } from "./factory-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[factory-language] retains source identity, expanded governance and pending source draft across language changes", async ({
  page,
  context,
}, testInfo) => {
  const state = await installFactoryFixture(page);
  await page.goto("/workspace/internal?view=factory");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: "Data sources", exact: true })).toBeVisible();
  await expect(page.locator(".ingestion-run-progress")).toContainText("Discovering versions · 3 objects observed");
  await expect(page.getByText("No new versions in this run", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  const sourceDetails = page.locator(".factory-source-details");
  await sourceDetails.locator("summary").click();
  await expect(sourceDetails).toHaveAttribute("open", "");
  await expect(sourceDetails).toContainText(factorySource.owner);
  await page.getByRole("button", { name: `Edit ${factorySource.name}`, exact: true }).click();
  const editor = page.getByRole("dialog", { name: "Edit source governance", exact: true });
  await editor.getByLabel("Source name", { exact: true }).fill("原始未提交草稿");
  state.holdSource = true;
  await editor.getByRole("button", { name: "Save", exact: true }).click();
  await expect(editor).toHaveAttribute("aria-busy", "true");
  await expect(editor.getByLabel("Source name", { exact: true })).toBeDisabled();
  await expect(editor.getByLabel("Data owner", { exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installFactoryFixture(second, state);
  await second.goto("/workspace/internal?view=factory");
  await selectInterfaceLanguage(second, "zh-CN");
  const chineseEditor = page.getByRole("dialog", { name: "编辑数据源治理配置", exact: true });
  await expect(chineseEditor.getByLabel("数据源名称", { exact: true })).toHaveValue("原始未提交草稿");
  await expect(chineseEditor.getByRole("button", { name: "关闭", exact: true })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(chineseEditor).toBeVisible();
  await expect(chineseEditor.locator("header").first()).toBeInViewport({ ratio: 1 });
  await expect(chineseEditor.locator(".form-actions")).toBeInViewport({ ratio: 1 });
  await page.screenshot({ path: testInfo.outputPath("factory-pending-source-zh.png"), animations: "disabled" });
  expect(state.writes).toEqual([`PATCH /api/v1/admin/data-sources/${factorySource.id}`]);
  state.release?.();
  await expect(chineseEditor).toHaveCount(0);
  await expect(sourceDetails).toHaveAttribute("open", "");
  await second.close();
  expect(state.errors).toEqual([]);
});

test("[factory-language] keeps immutable preview and quarantine evidence literal, and hides cached versions after denial", async ({
  page,
}, testInfo) => {
  const state = await installFactoryFixture(page);
  await page.goto("/workspace/internal?view=factory");
  await page.getByRole("button", { name: `View versions of ${factoryAsset.file_name}`, exact: true }).click();
  const drawer = page.getByRole("dialog", { name: factoryAsset.file_name, exact: true });
  await drawer.getByRole("button", { name: "View parsed text", exact: true }).click();
  await expect(drawer.getByText("原始科学正文 <EGFR>", { exact: true })).toBeVisible();
  // Use the language authority in another page so the modal's isolated background stays isolated.
  const second = await page.context().newPage();
  await installFactoryFixture(second, state);
  await second.goto("/workspace/internal?view=factory");
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(drawer.getByRole("heading", { name: "解析文本预览", exact: true })).toBeVisible();
  await expect(drawer.getByText("原始科学正文 <EGFR>", { exact: true })).toBeVisible();
  state.assetDenied = true;
  await drawer.getByRole("button", { name: "刷新源对象版本", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_ASSET_DENIAL");
  await expect(page.getByText("原始科学正文 <EGFR>", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "关闭源对象详情", exact: true }).last().click();
  await page.getByRole("button", { name: "处置", exact: true }).click();
  const quarantine = page.getByRole("dialog", { name: "隔离案件处置", exact: true });
  await expect(quarantine).toContainText(factoryQuarantine.threat_name ?? "");
  await expect(quarantine).toContainText("原始扫描诊断 <Source>");
  await quarantine.getByLabel("处置原因", { exact: true }).fill("原始处置草稿");
  await selectInterfaceLanguage(second, "en");
  const englishQuarantine = page.getByRole("dialog", { name: "Quarantine decision", exact: true });
  await expect(englishQuarantine.getByLabel("Decision reason", { exact: true })).toHaveValue("原始处置草稿");
  await englishQuarantine.getByLabel("Decision reason", { exact: true }).scrollIntoViewIfNeeded();
  await expect(englishQuarantine.locator("header").first()).toBeInViewport({ ratio: 1 });
  await expect(englishQuarantine.locator(".form-actions")).toBeInViewport({ ratio: 1 });
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("factory-quarantine-en.png"), animations: "disabled" });
  await second.close();
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});
