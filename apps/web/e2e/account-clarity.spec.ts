import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { installGovernanceFixture } from "./governance-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[account-clarity] fits original unbroken identity values without hiding them or shrinking their icon", async ({
  page,
}, testInfo) => {
  const state = await installGovernanceFixture(page);
  const originalName = `Researcher${"X".repeat(80)}`;
  const originalEmail = `${"original".repeat(6)}@source.example.test`;
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        id: "controlled-user",
        tenant_id: "controlled-tenant",
        email: originalEmail,
        display_name: originalName,
        role: "admin",
      },
    }),
  );
  await page.goto("/workspace/research?view=overview");
  await expect(page.locator("#user-center-identity-title")).toHaveText(originalName);
  await expect(page.locator(".user-center-identity-copy span")).toHaveText(originalEmail);
  const bounds = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    icon: document.querySelector(".user-center-identity-copy svg")?.getBoundingClientRect().width,
  }));
  expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
  expect(bounds.icon).toBe(15);
  expect(state.errors).toEqual([]);
  expect(state.writes).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("account-long-identity-en.png"), animations: "disabled" });
});

test("[account-clarity] keeps identity truthful and compact while recovery disclosure and profile drafts survive language changes", async ({
  page,
}, testInfo) => {
  const state = await installGovernanceFixture(page);
  await page.goto("/workspace/research?view=overview");
  await expect(page.getByText("Email ownership is unverified.", { exact: true })).toBeVisible();
  await expect(page.getByText("Account active", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Account details", { exact: true })).toHaveCount(0);
  const disclosure = page.locator(".user-center-sign-in-note details");
  const guidance = disclosure.locator("p");
  await expect(disclosure).not.toHaveAttribute("open", "");
  await expect(guidance).toBeHidden();
  await page.getByRole("textbox", { name: "Display name", exact: true }).fill("Unsubmitted original 科研");
  await page.screenshot({ path: testInfo.outputPath("account-compact-en.png"), animations: "disabled" });
  const summary = disclosure.locator("summary");
  await summary.focus();
  await summary.press("Space");
  await expect(guidance).toBeVisible();
  const originalName = await page.locator("#user-center-identity-title").innerText();
  const reads = { ...state.reads };
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByText("邮箱归属未验证。", { exact: true })).toBeVisible();
  await expect(summary).toHaveText("登录与恢复说明");
  await expect(disclosure).toHaveAttribute("open", "");
  await expect(page.getByRole("textbox", { name: "用户名", exact: true })).toHaveValue("Unsubmitted original 科研");
  await expect(page.locator("#user-center-identity-title")).toHaveText(originalName);
  expect(state.reads).toEqual(reads);
  expect(state.writes).toEqual([]);
  const geometry = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(geometry.document).toBeLessThanOrEqual(geometry.viewport);
  expect(
    (await new AxeBuilder({ page }).include("main").withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("account-disclosure-zh.png"), animations: "disabled" });
  await summary.focus();
  await summary.press("Enter");
  await expect(guidance).toBeHidden();
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("textbox", { name: "Display name", exact: true })).toHaveValue(
    "Unsubmitted original 科研",
  );
  expect(state.errors).toEqual([]);
  expect(state.writes).toEqual([]);
});
