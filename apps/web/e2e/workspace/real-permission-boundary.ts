import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";

export async function verifyRealPermissionBoundary(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(120_000);
  const email = process.env.E2E_PERMISSION_EMAIL;
  const password = process.env.E2E_PERMISSION_PASSWORD;
  test.skip(!email || !password, "Real viewer permission credentials are required");
  if (!email || !password) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const externalRead = await page.request.get("/api/v1/entities?limit=1&offset=0");
  expect(externalRead.status()).toBe(200);
  const internalRead = await page.request.get("/api/v1/enterprise/overview");
  expect(internalRead.status()).toBe(403);

  await page.goto("/workspace/internal?view=governance");
  await expect(page.getByText("无权访问该工作区", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "数据工厂" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "商业运营" })).toHaveCount(0);

  await page.goto("/workspace/research?view=explorer");
  await expect(page.getByRole("heading", { name: "全局情报检索", level: 1 })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("无权访问该工作区");
}
