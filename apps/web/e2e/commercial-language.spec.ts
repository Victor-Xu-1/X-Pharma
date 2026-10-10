import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { controlledCommercialClient, installCommercialFixture } from "./commercial-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[commercial-language] preserves the captured client intent and original reason while language changes", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installCommercialFixture(page);
  await page.goto("/workspace/internal?view=commercial");
  await page.getByRole("tab", { name: "Clients", exact: true }).click();
  await page.getByRole("button", { name: "Disable " + controlledCommercialClient.display_name, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Disable client", exact: true });
  await dialog.getByRole("textbox", { name: "Reason", exact: true }).fill("Original operator basis <source>");
  state.hold = true;
  await dialog.getByRole("button", { name: "Confirm disable", exact: true }).click();
  await expect(dialog.getByRole("textbox", { name: "Reason", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Billing", exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installCommercialFixture(second);
  await second.goto("/workspace/internal?view=commercial");
  const previousReads = state.reads;
  await selectInterfaceLanguage(second, "zh-CN");
  const chinese = page.getByRole("dialog", { name: "停用客户端", exact: true });
  await expect(chinese.getByRole("textbox", { name: "操作原因", exact: true })).toHaveValue(
    "Original operator basis <source>",
  );
  await expect(chinese.getByText(controlledCommercialClient.client_key, { exact: true })).toBeVisible();
  await expect(chinese.getByRole("button", { name: "关闭", exact: true })).toBeDisabled();
  expect(state.reads).toBe(previousReads);
  expect(state.writes).toEqual([{ active: false, reason: "Original operator basis <source>" }]);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".modal-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("commercial-client-pending-zh.png"), animations: "disabled" });
  state.release?.();
  await expect(chinese).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "启用 " + controlledCommercialClient.display_name, exact: true }),
  ).toBeVisible();
  state.denied = true;
  await page.getByRole("button", { name: "刷新", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_COMMERCIAL_DENIAL");
  await expect(page.getByText(controlledCommercialClient.display_name, { exact: true })).toHaveCount(0);
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  await second.close();
});
test("[commercial-layout] leaves the language selector and refresh action unobscured", async ({ page }, testInfo) => {
  const { base } = await installCommercialFixture(page);
  await page.goto("/workspace/internal?view=commercial");
  const language = page.getByRole("combobox", { name: "Interface language", exact: true });
  const refresh = page.getByRole("button", { name: "Refresh", exact: true });
  await expect(refresh).toBeEnabled();
  const a = await language.boundingBox(),
    b = await refresh.boundingBox();
  if (!a || !b) throw new Error("Commercial header controls are missing");
  expect(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y).toBe(true);
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("tab", { name: "合同与额度", exact: true })).toBeVisible();
  const bounds = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".commercial-workbench")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("commercial-header-zh.png"), animations: "disabled" });
  expect(base.errors).toEqual([]);
});

test("[commercial-policy] keeps grouped fields, original licensing text and one shared policy intent", async ({
  page,
}, testInfo) => {
  const { base, state } = await installCommercialFixture(page);
  await page.goto("/workspace/internal?view=commercial");
  await page.getByRole("tab", { name: "Export policy", exact: true }).click();
  await page.getByRole("heading", { name: "Workspace export policy", exact: true }).waitFor();
  await page
    .locator(".policy-field-group > summary")
    .filter({ hasText: /^Entity search/ })
    .click();
  await page.getByRole("textbox", { name: "Policy version", exact: true }).fill("ORIGINAL_POLICY_V2");
  await page.getByRole("textbox", { name: "Attribution", exact: true }).fill("Original licensing text <source>");
  await page.getByRole("tab", { name: "Contracts & quota", exact: true }).click();
  await page.getByRole("tab", { name: "Export policy", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Attribution", exact: true })).toHaveValue(
    "Original licensing text <source>",
  );
  await expect(
    page.locator(".policy-field-group").filter({ has: page.locator("summary").filter({ hasText: /^Entity search/ }) }),
  ).toHaveAttribute("open", "");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(
    page.locator(".policy-field-group").filter({ has: page.locator("summary").filter({ hasText: /^实体检索/ }) }),
  ).toHaveAttribute("open", "");
  state.holdPolicy = true;
  await page.getByRole("button", { name: "保存导出策略", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "策略版本", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: "CSV", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Agent 客户端", exact: true })).toBeDisabled();
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("textbox", { name: "Attribution", exact: true })).toHaveValue(
    "Original licensing text <source>",
  );
  expect(state.policyWrites).toHaveLength(1);
  expect(state.policyWrites[0]).toMatchObject({
    policy_version: "ORIGINAL_POLICY_V2",
    attribution: "Original licensing text <source>",
  });
  expect(
    (
      await new AxeBuilder({ page })
        .include(".export-policy-admin")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("commercial-policy-pending-en.png"), animations: "disabled" });
  state.releasePolicy?.();
  await expect(page.getByRole("status")).toContainText("Export policy ORIGINAL_POLICY_V2 is active");
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
});

test("[commercial-policy] retains stale unsent licensing and unknown field IDs until explicitly adopting a new policy", async ({
  page,
}, testInfo) => {
  const { base, state } = await installCommercialFixture(page);
  state.policy = {
    id: "controlled-policy",
    policy_version: "original-v1",
    policy_sha256: "a".repeat(64),
    enabled: true,
    allowed_formats: ["csv"],
    allowed_fields: ["id", "entity_type", "name", "unknown.source_field"],
    attribution: "Original licensing <source>",
    max_records_per_export: 25,
    configured_by_user_id: "controlled-admin",
    created_at: "2026-10-10T00:00:00Z",
    updated_at: "2026-10-10T00:00:00Z",
  };
  await page.goto("/workspace/internal?view=commercial");
  await page.getByRole("tab", { name: "Export policy", exact: true }).click();
  const attribution = page.getByRole("textbox", { name: "Attribution", exact: true });
  await expect(attribution).toHaveValue("Original licensing <source>");
  const general = page
    .locator(".policy-field-group")
    .filter({ has: page.locator("summary").filter({ hasText: /^General fields/ }) });
  await expect(general).not.toHaveAttribute("open", "");
  await expect(page.getByText("unknown.source_field", { exact: true })).toBeVisible();
  const versionBounds = await page.getByRole("textbox", { name: "Policy version", exact: true }).boundingBox();
  const fieldsBounds = await general.boundingBox();
  if (!versionBounds || !fieldsBounds) throw new Error("Policy controls are missing");
  expect(versionBounds.y + versionBounds.height).toBeLessThan(fieldsBounds.y);
  await attribution.fill("Unsubmitted licensing <source>");
  state.policy = {
    ...state.policy,
    policy_version: "new-v2",
    attribution: "Updated licensing <source>",
    policy_sha256: "b".repeat(64),
  };
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByRole("button", { name: "Use latest policy", exact: true })).toBeVisible();
  await expect(attribution).toHaveValue("Unsubmitted licensing <source>");
  await expect(page.getByRole("button", { name: "Save export policy", exact: true })).toBeDisabled();
  const reads = state.policyReads;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "授权标注", exact: true })).toHaveValue(
    "Unsubmitted licensing <source>",
  );
  expect(state.policyReads).toBe(reads);
  expect(state.policyWrites).toEqual([]);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".export-policy-admin")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("commercial-policy-conflict-zh.png"), animations: "disabled" });
  await page.getByRole("button", { name: "使用最新策略", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "授权标注", exact: true })).toHaveValue("Updated licensing <source>");
  await expect(page.getByRole("textbox", { name: "策略版本", exact: true })).toHaveValue("new-v2");
  await expect(page.getByText("unknown.source_field", { exact: true })).toBeVisible();
  const bounds = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
  expect(state.policyWrites).toEqual([]);
  expect(base.writes).toEqual([]);
  expect(base.errors).toEqual([]);
});
