import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import type { PublicKnowledgePageSearchResult } from "../../src/lib/generated";

export async function verifyKnowledgeResearchContinuity(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "Authenticated browser fixture credentials are required");
  if (!credentials) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const pagesResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/v1/knowledge/pages/search";
  });
  await page.goto("/workspace/research?view=knowledge");
  const pagesResponse = await pagesResponsePromise;
  expect(pagesResponse.ok()).toBe(true);
  const pages = (await pagesResponse.json()) as PublicKnowledgePageSearchResult;
  expect(pages.limit).toBe(50);
  expect(pages.offset).toBe(0);
  expect(pages.total).toBeGreaterThanOrEqual(pages.items.length);
  const topic = pages.items.find((item) => /^[0-9a-f-]{36}$/i.test(item.id));
  expect(topic, "the authenticated tenant must expose at least one governed knowledge topic").toBeTruthy();
  if (!topic) return;

  const topicButton = page.locator(".knowledge-page-list button").filter({ hasText: topic.title }).first();
  await expect(topicButton).toBeVisible();
  await topicButton.click();
  await expect(page).toHaveURL(new RegExp(`view=knowledge.*page=${topic.id}`));
  await expect(page.getByRole("heading", { name: topic.title, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: topic.title, exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "覆盖与版本" }).click();
  await expect(page).toHaveURL(new RegExp(`page=${topic.id}.*panel=coverage`));
  const versionList = page.getByRole("list", { name: "专题版本" });
  const versionButton = versionList.getByRole("button").first();
  await expect(versionButton).toBeVisible();
  const versionLabel = (await versionButton.getByRole("strong").textContent())?.trim() ?? "";
  const versionNumber = Number.parseInt(versionLabel.replace(/^v/, ""), 10);
  expect(versionNumber).toBeGreaterThan(0);
  await versionButton.click();
  await expect(page).toHaveURL(new RegExp(`panel=coverage.*version=${versionNumber}`));
  await page.reload();
  await expect(versionButton).toHaveAttribute("aria-current", "true");

  await page.goBack();
  await expect(page).toHaveURL(/panel=coverage/);
  await expect(page).not.toHaveURL(/version=/);
  await expect(page.getByRole("tab", { name: "覆盖与版本" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).not.toHaveURL(/panel=/);
  await expect(page.getByRole("tab", { name: "专题正文" })).toHaveAttribute("aria-selected", "true");
}
