import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyInternalLogin({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  await page.goto("/workspace/internal");
  await selectInterfaceLanguage(page, "zh-CN");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByRole("heading", { name: "内部管理工作台" })).toBeVisible();
  await expect(page.getByLabel("内部管理平台", { exact: true })).toBeVisible();
  await expect(page.getByText("医药情报工作台", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("X-Pharma", { exact: true })).toHaveCount(0);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
