import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { selectInterfaceLanguage } from "./interface-language";
import { controlledProjectionJob, installPublicationFixture } from "./publication-fixture";

test("[publication-language] keeps immutable preview, draft and shared-operation lock across bilingual changes", async ({
  page,
  context,
}, testInfo) => {
  const state = await installPublicationFixture(page);
  await page.goto("/workspace/internal?view=governance");
  await page.getByText("Batch publication and withdrawal", { exact: true }).click();
  await page.getByRole("checkbox", { name: /原始药物 A/ }).check();
  await page.getByRole("textbox", { name: "Batch review evidence", exact: true }).fill("原始 batch basis <source>");
  state.holdPreview = true;
  await page.getByRole("button", { name: "Preview publication (1)", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Batch review evidence", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve and publish", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: /^Entity resolution/ })).toBeDisabled();
  const second = await context.newPage();
  await installPublicationFixture(second, state);
  await second.goto("/workspace/internal?view=governance");
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(page.getByRole("textbox", { name: "批次审核依据", exact: true })).toHaveValue(
    "原始 batch basis <source>",
  );
  expect(state.writes).toEqual(["POST /api/v1/governance/publication-batches/preview"]);
  state.releasePreview?.();
  const commit = page.getByRole("button", { name: "原子提交发布", exact: true });
  await expect(commit).toBeEnabled();
  await page.getByText("预览指纹", { exact: true }).click();
  await expect(page.getByText("a".repeat(64), { exact: true })).toBeVisible();
  state.holdCommit = true;
  await commit.click();
  await expect(page.getByRole("textbox", { name: "审核意见", exact: true })).toBeDisabled();
  await selectInterfaceLanguage(second, "en");
  await expect(page.getByRole("button", { name: "Commit publication atomically", exact: true })).toBeDisabled();
  expect(
    (
      await new AxeBuilder({ page })
        .include(".publication-control")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("publication-pending-en.png"), animations: "disabled" });
  state.releaseCommit?.();
  await expect(page.getByRole("button", { name: "Preview withdrawal of this batch", exact: true })).toBeEnabled();
  state.batchDenied = true;
  await page.getByRole("button", { name: "Refresh batch details", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_BATCH_DENIAL");
  await expect(page.getByText("a".repeat(64), { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Preview withdrawal of this batch", exact: true })).toHaveCount(0);
  expect(state.writes.length).toBe(2);
  expect(state.errors).toEqual([]);
  await second.close();
});

test("[projection-confirm] requires explicit global-rebuild confirmation and retains it during a pending request", async ({
  page,
  context,
}, testInfo) => {
  const state = await installPublicationFixture(page);
  state.privileged = true;
  state.jobs = [controlledProjectionJob];
  await page.goto("/workspace/internal?view=governance");
  await page.getByText("Batch publication and withdrawal", { exact: true }).click();
  await expect(page.getByText("Not reported / 12", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Atomic global projection rebuild", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Rebuild global search projections", exact: true });
  await expect(dialog.getByRole("button", { name: "Confirm rebuild", exact: true })).toBeDisabled();
  expect(state.writes).toEqual([]);
  await dialog.getByRole("checkbox").check();
  state.holdMaintenance = true;
  await dialog.getByRole("button", { name: "Confirm rebuild", exact: true }).click();
  await expect(dialog).toHaveAttribute("aria-busy", "true");
  await expect(dialog.getByRole("button", { name: "Close rebuild confirmation", exact: true })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();
  const second = await context.newPage();
  await installPublicationFixture(second, state);
  await second.goto("/workspace/internal?view=governance");
  await selectInterfaceLanguage(second, "zh-CN");
  const chinese = page.getByRole("dialog", { name: "重建全局检索投影", exact: true });
  await expect(chinese.getByRole("checkbox")).toBeChecked();
  await expect(chinese.getByRole("button", { name: "取消", exact: true })).toBeDisabled();
  await expect(chinese.locator("header")).toBeInViewport({ ratio: 1 });
  await expect(chinese.locator("footer")).toBeInViewport({ ratio: 1 });
  expect(
    (
      await new AxeBuilder({ page })
        .include(".projection-rebuild-dialog")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("projection-confirm-pending-zh.png"), animations: "disabled" });
  state.releaseMaintenance?.();
  await expect(chinese).toHaveCount(0);
  await expect(page.getByText("维护任务已受理", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "一致性检查", exact: true })).toBeDisabled();
  state.accessDenied = true;
  await page.getByRole("button", { name: "刷新投影任务", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_GLOBAL_ACCESS_DENIAL");
  await expect(page.getByRole("button", { name: "原子重建全局投影", exact: true })).toHaveCount(0);
  expect(state.writes).toEqual(["POST /api/v1/governance/projection-maintenance-jobs"]);
  expect(state.errors).toEqual([]);
  await second.close();
});
