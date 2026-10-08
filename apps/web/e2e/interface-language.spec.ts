import { expect, test } from "@playwright/test";
import { selectInterfaceLanguage } from "./interface-language";

for (const workbench of ["research", "internal"] as const) {
  test(`[bilingual-interface] ${workbench} starts in English and preserves drafts and the explicit locale choice`, async ({
    page,
  }) => {
    const writes: string[] = [];
    await page.route("**/api/v1/**", (route) => {
      const request = route.request();
      if (["GET", "HEAD", "OPTIONS"].includes(request.method())) return route.continue();
      writes.push(`${request.method()} ${new URL(request.url()).pathname}`);
      return route.abort("blockedbyclient");
    });
    await page.goto(`/workspace/${workbench}`);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Interface language", exact: true })).toHaveValue("en");
    await page.getByLabel("Work email", { exact: true }).fill("language-draft@example.test");
    const originalURL = page.url();
    await selectInterfaceLanguage(page, "zh-CN");
    await expect(page.getByLabel("工作邮箱", { exact: true })).toHaveValue("language-draft@example.test");
    expect(page.url()).toBe(originalURL);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
    await expect(page.getByRole("heading", { name: "账户登录", exact: true })).toBeVisible();
    await selectInterfaceLanguage(page, "en");
    await page.reload();
    await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open workbench", exact: true })).toBeDisabled();
    const bounds = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(writes).toEqual([]);
  });
}
