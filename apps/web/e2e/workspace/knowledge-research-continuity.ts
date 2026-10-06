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

  // Controlled layout responses reproduce a narrow index with >500 topics.
  // They do not create governed pages or replace real publication evidence.
  const pattern = "**/api/v1/knowledge/pages/search*";
  await page.route(pattern, async (route) => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset") ?? 0);
    const count = Math.min(50, 503 - offset);
    await route.fulfill({
      json: {
        ...pages,
        total: 503,
        offset,
        limit: 50,
        items: Array.from({ length: count }, (_, index) => ({
          ...topic,
          id: `00000000-0000-4000-8000-${String(offset + index + 1).padStart(12, "0")}`,
          title: `Controlled pagination layout ${offset + index + 1}`,
        })),
      },
    });
  });
  try {
    await page.goto("/workspace/research?view=knowledge&offset=450");
    await expect(page.locator(".knowledge-page-list button")).toHaveCount(50);
    const pagination = page.getByRole("navigation", { name: "知识专题分页" });
    await pagination.getByRole("button", { name: "末页", exact: true }).click();
    await expect(page).toHaveURL(/offset=500/);
    await expect(page.locator(".knowledge-page-list button")).toHaveCount(3);
    await pagination.getByLabel("目标页码").fill("99");
    await pagination.getByRole("button", { name: "跳转", exact: true }).click();
    await expect(pagination.getByRole("alert")).toContainText("1 到 11");
    await pagination.getByLabel("目标页码").fill("1");
    await pagination.getByRole("button", { name: "跳转", exact: true }).click();
    await expect(page.locator(".knowledge-page-list button")).toHaveCount(50);
  } finally {
    await page.unroute(pattern);
  }
}
