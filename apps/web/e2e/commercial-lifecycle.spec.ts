import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { controlledSourceAsset, installCommercialLifecycleFixture } from "./commercial-lifecycle-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[commercial-lifecycle-drafts] retains drafts, accepts whole-hour input and reconciles a newer policy explicitly", async ({
  page,
}, testInfo) => {
  const { base, state } = await installCommercialLifecycleFixture(page);
  await page.goto("/workspace/internal?view=commercial");
  await page.getByRole("tab", { name: "Data lifecycle", exact: true }).click();
  const basis = page.getByRole("textbox", { name: "Legal or contractual basis", exact: true });
  const form = page.locator("form").filter({ has: basis });
  await expect(form.getByText("Inactive", { exact: true })).toBeVisible();
  await page.getByRole("spinbutton", { name: "Retention period (hours)", exact: true }).fill("48");
  await basis.fill("Unsubmitted legal basis <source>");
  await page.getByRole("textbox", { name: "Matter reference", exact: true }).fill("UNSUBMITTED_MATTER");
  expect(await form.evaluate((node) => (node as HTMLFormElement).checkValidity())).toBe(true);
  await page.getByRole("tab", { name: "Clients", exact: true }).click();
  await page.getByRole("tab", { name: "Data lifecycle", exact: true }).click();
  await expect(basis).toHaveValue("Unsubmitted legal basis <source>");
  await expect(page.getByRole("textbox", { name: "Matter reference", exact: true })).toHaveValue("UNSUBMITTED_MATTER");
  state.policies = [
    { ...state.policies[0], policy_version: 3, legal_basis: "New server basis <source>" },
    ...state.policies.slice(1),
  ];
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(form.getByRole("button", { name: "Use latest policy", exact: true })).toBeVisible();
  await expect(basis).toHaveValue("Unsubmitted legal basis <source>");
  await expect(form.getByRole("button", { name: "Save policy", exact: true })).toBeDisabled();
  await form.getByRole("button", { name: "Use latest policy", exact: true }).click();
  await expect(basis).toHaveValue("New server basis <source>");
  await page.getByRole("spinbutton", { name: "Retention period (hours)", exact: true }).fill("48");
  state.hold = true;
  await form.getByRole("button", { name: "Save policy", exact: true }).click();
  await expect(basis).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Clients", exact: true })).toBeDisabled();
  const reads = state.reads;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "法律与合同依据", exact: true })).toHaveValue(
    "New server basis <source>",
  );
  await expect(page.getByRole("textbox", { name: "事项编号", exact: true })).toHaveValue("UNSUBMITTED_MATTER");
  expect(state.reads).toBe(reads);
  expect(state.writes).toEqual([
    { retention_seconds: 172800, legal_basis: "New server basis <source>", geographic_scope: ["CN"], active: false },
  ]);
  await page.screenshot({ path: testInfo.outputPath("lifecycle-policy-pending-zh.png"), animations: "disabled" });
  state.release?.();
  await expect(page.getByRole("textbox", { name: "法律与合同依据", exact: true })).toBeEnabled();
  expect(base.base.errors).toEqual([]);
  expect(base.base.writes).toEqual([]);
});
test("[commercial-lifecycle-intent] presents literal targets, requires acknowledgement and preserves the retry intent", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installCommercialLifecycleFixture(page);
  await page.goto("/workspace/internal?view=commercial");
  await page.getByRole("tab", { name: "Data lifecycle", exact: true }).click();
  const opener = page.getByRole("button", {
    name: "Withdraw source asset " + controlledSourceAsset.file_name,
    exact: true,
  });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Withdraw source asset", exact: true });
  await expect(dialog.getByText(controlledSourceAsset.id, { exact: true })).toBeVisible();
  await expect(dialog.getByText(controlledSourceAsset.logical_path, { exact: true })).toBeVisible();
  await dialog.getByRole("textbox", { name: "Lifecycle action reason", exact: true }).fill("Original basis <source>");
  await expect(dialog.getByRole("button", { name: "Confirm action", exact: true })).toBeDisabled();
  await dialog
    .getByRole("checkbox", { name: "I have checked the target and understand this action", exact: true })
    .check();
  await dialog.getByRole("button", { name: "Confirm action", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("RAW_CONTROLLED_PURGE_FAILURE");
  await expect(dialog.getByRole("textbox", { name: "Lifecycle action reason", exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installCommercialLifecycleFixture(second);
  await second.goto("/workspace/internal?view=commercial");
  await selectInterfaceLanguage(second, "zh-CN");
  const chinese = page.getByRole("dialog", { name: "撤回源资料", exact: true });
  await expect(chinese.getByRole("textbox", { name: "生命周期操作原因", exact: true })).toHaveValue(
    "Original basis <source>",
  );
  await chinese.getByRole("button", { name: "确认执行", exact: true }).click();
  await expect.poll(() => state.writes.length).toBe(2);
  expect(state.writes[1]).toEqual(state.writes[0]);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".modal-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const geometry = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(geometry.document).toBeLessThanOrEqual(geometry.viewport);
  await page.screenshot({ path: testInfo.outputPath("lifecycle-withdrawal-retry-zh.png"), animations: "disabled" });
  await chinese.getByRole("button", { name: "取消", exact: true }).click();
  await expect(chinese).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "撤回源资料 " + controlledSourceAsset.file_name, exact: true }),
  ).toBeFocused();
  expect(base.base.errors).toEqual([]);
  expect(base.base.writes).toEqual([]);
  await second.close();
});
