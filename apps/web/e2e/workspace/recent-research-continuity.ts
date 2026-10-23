import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyRecentResearchContinuity(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const targetId = process.env.E2E_PIPELINE_TARGET_ID;
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !targetId || !fixtureKey, "Authenticated research fixtures are required");
  if (!credentials || !targetId || !fixtureKey) return;
  const name = `Browser pipeline target ${fixtureKey}`;
  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await page.goto(`/workspace/research?view=target&entity=${targetId}`);
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  await page.goto("/workspace/research?view=explorer");
  await page.getByRole("button", { name: "继续最近的研究" }).click();
  const resume = page.getByRole("button", { name: `继续研究 ${name}` });
  await expect(resume).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "继续最近的研究" }).click();
  await expect(resume).toBeVisible();
  await resume.click();
  await expect.poll(() => new URL(page.url()).searchParams.get("entity")).toBe(targetId);
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}
