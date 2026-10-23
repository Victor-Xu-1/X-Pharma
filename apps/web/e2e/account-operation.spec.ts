import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import type { OrganizationRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test.use({ trace: "off" });
async function fixture(page: Page) {
  const base = await installGovernanceFixture(page);
  const membership: OrganizationRead = {
    tenant_id: "controlled-tenant",
    slug: "original",
    name: "Original organization <source>",
    active: true,
    selected: true,
    role: "admin",
  };
  const state = {
    profile: [] as unknown[],
    joins: [] as unknown[],
    membershipReads: 0,
    release: undefined as (() => void) | undefined,
  };
  await page.route("**/api/v1/auth/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET" && path === "/api/v1/auth/organizations") {
      state.membershipReads++;
      return route.fulfill({ json: [membership] });
    }
    if (
      (request.method() === "PATCH" && path === "/api/v1/auth/me") ||
      (request.method() === "POST" && path === "/api/v1/auth/organizations/join")
    ) {
      (path.endsWith("/join") ? state.joins : state.profile).push(request.postDataJSON());
      await new Promise<void>((resolve) => {
        state.release = resolve;
      });
      return route.fulfill({ status: 503, json: { detail: "PRIVATE_CONTROLLED_IDENTITY_FAILURE" } });
    }
    return route.fallback();
  });
  return { base, state };
}

test("[account-operation] preserves bilingual account intent and blocks repeated submission and pending organization dismissal", async ({
  page,
  context,
}, testInfo) => {
  const { base, state } = await fixture(page);
  await page.goto("/workspace/research?view=overview");
  await page.getByRole("textbox", { name: "Display name", exact: true }).fill("Original unsaved researcher 科研");
  const save = page.getByRole("button", { name: "Save profile", exact: true });
  await save.click();
  await expect(save).toBeDisabled();
  await expect(page.getByRole("textbox", { name: "Display name", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Sign out of this account", exact: true })).toBeDisabled();
  await page
    .locator(".user-center-form")
    .first()
    .evaluate((form) => (form as HTMLFormElement).requestSubmit());
  const profileReads = { ...base.reads };
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "用户名", exact: true })).toHaveValue(
    "Original unsaved researcher 科研",
  );
  expect(base.reads).toEqual(profileReads);
  expect(state.profile).toEqual([
    {
      display_name: "Original unsaved researcher 科研",
      email: "controlled@example.test",
      phone: null,
      avatar_url: null,
    },
  ]);
  state.release?.();
  await expect(page.getByRole("alert")).toContainText("个人资料保存失败");
  await expect(page.getByText("PRIVATE_CONTROLLED_IDENTITY_FAILURE", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "用户名", exact: true })).toBeEnabled();
  const navigation = page.getByRole("button", { name: "打开导航", exact: true });
  if (await navigation.isVisible()) await navigation.click();
  const opener = page.getByRole("button", { name: "组织与账号", exact: true });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "组织与账号", exact: true });
  await expect(dialog.getByText("Original organization <source>", { exact: true })).toBeVisible();
  await dialog.getByLabel("管理员邀请码").fill("CONTROLLED-NOT-A-REAL-CODE");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "确认加入组织", exact: true }).click();
  await expect(dialog.getByLabel("管理员邀请码")).toBeDisabled();
  await expect(dialog.getByRole("checkbox")).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "关闭", exact: true })).toBeDisabled();
  await dialog.press("Escape");
  await expect(dialog).toBeVisible();
  await dialog.locator("form").evaluate((form) => (form as HTMLFormElement).requestSubmit());
  const other = await context.newPage();
  await fixture(other);
  await other.goto("/workspace/research?view=overview");
  const membershipReads = state.membershipReads;
  await selectInterfaceLanguage(other, "en");
  const english = page.getByRole("dialog", { name: "Organizations & account", exact: true });
  await expect(english.getByLabel("Administrator invitation code")).toHaveValue("CONTROLLED-NOT-A-REAL-CODE");
  expect(state.membershipReads).toBe(membershipReads);
  expect(state.joins).toEqual([{ invitation_code: "CONTROLLED-NOT-A-REAL-CODE", confirmed: true }]);
  state.release?.();
  await expect(english.getByRole("alert")).toContainText("Could not accept the invitation. Please try again.");
  await expect(english.getByLabel("Administrator invitation code")).toHaveValue("");
  expect(
    (
      await new AxeBuilder({ page })
        .include(".organization-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const geometry = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(geometry.document).toBeLessThanOrEqual(geometry.viewport);
  await page.screenshot({ path: testInfo.outputPath("account-organization-rejected-en.png"), animations: "disabled" });
  await english.press("Escape");
  await expect(english).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Organizations & account", exact: true })).toBeFocused();
  expect(base.errors).toEqual([]);
  expect(base.writes).toEqual([]);
  await other.close();
});
