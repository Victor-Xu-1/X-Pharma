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

test("[enterprise-language] keeps audit filters visible while replacing a previous page and preserves an unsubmitted action across languages", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installEnterpriseLanguageFixture(page);
  state.audit = {
    items: [
      {
        id: "original-audit",
        action: "ORIGINAL_AUDIT_ACTION",
        actor_id: "Original actor",
        actor_type: "user",
        details: {},
        occurred_at: "2026-10-11T00:00:00Z",
        outcome: "success",
        request_id: "Original request",
        resource_id: null,
        resource_type: "Original resource",
      },
    ],
    next_cursor: "ORIGINAL_CURSOR",
  };
  await page.goto("/workspace/internal?view=enterprise");
  await page.getByRole("tab", { name: "Audit log", exact: true }).click();
  await expect(page.getByText("ORIGINAL_AUDIT_ACTION", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Audit action", exact: true }).fill("Unsubmitted.original.action");
  state.auditHold = true;
  state.audit = { items: [], next_cursor: null };
  await page.getByRole("combobox", { name: "Actor type", exact: true }).selectOption("agent");
  await expect(page.getByText("ORIGINAL_AUDIT_ACTION", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Actor type", exact: true })).toHaveValue("agent");
  const second = await context.newPage();
  await installEnterpriseLanguageFixture(second);
  await second.goto("/workspace/internal?view=enterprise");
  const reads = state.reads;
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(page.getByRole("textbox", { name: "审计动作", exact: true })).toHaveValue("Unsubmitted.original.action");
  expect(state.reads).toBe(reads);
  expect(state.auditFilters).toEqual([
    { actorType: null, action: null, cursor: null },
    { actorType: "agent", action: null, cursor: null },
  ]);
  state.auditHold = false;
  state.auditRelease?.();
  await expect(page.getByText("没有符合条件的审计事件", { exact: true })).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    const applyBounds = await page.getByRole("button", { name: "筛选", exact: true }).boundingBox();
    const clearBounds = await page.getByRole("button", { name: "清除筛选", exact: true }).boundingBox();
    expect(applyBounds && clearBounds && Math.abs(applyBounds.y - clearBounds.y)).toBeLessThanOrEqual(1);
  }
  expect(
    (
      await new AxeBuilder({ page })
        .include(".enterprise-workbench")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("enterprise-audit-filter-empty-zh.png"), animations: "disabled" });
  await page.getByRole("button", { name: "清除筛选", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "审计动作", exact: true })).toHaveValue("");
  await expect(page.getByRole("combobox", { name: "操作者类型", exact: true })).toHaveValue("");
  await expect(page.getByText("ORIGINAL_AUDIT_ACTION", { exact: true })).toBeVisible();
  // This exact unfiltered page remains within the normal query freshness window.
  // Returning to it may reuse its matching cache; changing filters must not.
  expect(state.auditFilters).toHaveLength(2);
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  expect(state.writes).toEqual([]);
  expect(state.invitationWrites).toEqual([]);
  await second.close();
});

test("[enterprise-language] preserves an invitation draft across tabs and languages, then freezes a single failed issuance without exposing private errors", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await installEnterpriseLanguageFixture(page);
  await page.goto("/workspace/internal?view=enterprise");
  await page.getByRole("tab", { name: "Registration invitations", exact: true }).click();
  const email = page.getByRole("textbox", { name: "Invited email", exact: true });
  await email.fill("Draft.original@example.test");
  await page.getByRole("spinbutton", { name: "Validity (hours)", exact: true }).fill("72");
  await page.getByRole("tab", { name: "Groups", exact: true }).click();
  await page.getByRole("tab", { name: "Registration invitations", exact: true }).click();
  await expect(email).toHaveValue("Draft.original@example.test");
  state.hold = state.fail = true;
  await page.getByRole("button", { name: "Issue registration invitation", exact: true }).click();
  await expect(email).toBeDisabled();
  await expect(page.getByRole("spinbutton", { name: "Validity (hours)", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Groups", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeDisabled();
  const second = await context.newPage();
  await installEnterpriseLanguageFixture(second);
  await second.goto("/workspace/internal?view=enterprise");
  const reads = state.reads;
  await selectInterfaceLanguage(second, "zh-CN");
  await expect(page.getByRole("textbox", { name: "受邀邮箱", exact: true })).toHaveValue("Draft.original@example.test");
  await expect(page.getByRole("spinbutton", { name: "有效小时", exact: true })).toHaveValue("72");
  expect(state.reads).toBe(reads);
  expect(state.invitationWrites).toEqual([
    { kind: "issue", payload: { email: "Draft.original@example.test", valid_hours: 72 } },
  ]);
  state.release?.();
  await expect(page.getByRole("alert")).toContainText("邀请操作失败，请稍后重试");
  await expect(page.getByRole("textbox", { name: "受邀邮箱", exact: true })).toBeEnabled();
  await expect(page.getByText("PRIVATE_CONTROLLED_INVITATION_FAILURE")).toHaveCount(0);
  await selectInterfaceLanguage(second, "en");
  await expect(page.getByRole("alert")).toContainText("Could not complete the invitation. Try again later.");
  await expect(email).toHaveValue("Draft.original@example.test");
  expect(state.reads).toBe(reads);
  expect(state.invitationWrites).toHaveLength(1);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".enterprise-workbench")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const geometry = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(geometry.document).toBeLessThanOrEqual(geometry.viewport);
  await page.screenshot({ path: testInfo.outputPath("enterprise-invitation-failed-en.png"), animations: "disabled" });
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  await second.close();
});
