import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyPublicLogin({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("research");
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "医药情报工作台" })).toBeVisible();
  await expect(page.getByLabel("X-Pharma", { exact: true })).toBeVisible();
  await expect(page.getByText("内部管理工作台", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("内部管理平台", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "进入工作台" })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
