import { expect } from "@playwright/test";
import { openNavigation } from "../helpers";
import type { verifyIngestionAndQuarantine } from "./ingestion-and-quarantine";

export async function verifyPublication(context: Awaited<ReturnType<typeof verifyIngestionAndQuarantine>>) {
  const { page, testInfo, fixtureKeyBase } = context;
  await openNavigation(page);
  const governanceRunsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/v1/governance/runs") && response.request().method() === "GET",
  );
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "AI 审核" }).click();
  await expect(page.getByRole("heading", { name: "AI 信息审核" })).toBeVisible();
  await page.getByText("批次发布与撤回", { exact: true }).click();
  const publicationQuote = `Browser publication evidence ${fixtureKeyBase} ${testInfo.project.name}`;
  const publicationFact = page.locator(".publication-fact-list label").filter({ hasText: publicationQuote });
  await expect(publicationFact).toBeVisible();
  await publicationFact.getByRole("checkbox").check();
  await page.getByRole("textbox", { name: "批次审核依据" }).fill(`Browser publication ${testInfo.project.name}`);
  const publicationPreviewResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/governance/publication-batches/preview") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().operation === "publish",
  );
  await page.getByRole("button", { name: "生成发布预览 (1)" }).click();
  const publicationPreviewResponse = await publicationPreviewResponsePromise;
  expect(publicationPreviewResponse.status()).toBe(201);
  const publicationPreview = (await publicationPreviewResponse.json()) as {
    id: string;
    operation: string;
    preview_sha256: string;
    status: string;
  };
  expect(publicationPreview).toMatchObject({ operation: "publish", status: "previewed" });
  expect(publicationPreview.preview_sha256).toMatch(/^[0-9a-f]{64}$/);
  const publicationCommitResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/publication-batches/${publicationPreview.id}/commit`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "原子提交发布" }).click();
  const publicationCommitResponse = await publicationCommitResponsePromise;
  expect(publicationCommitResponse.status()).toBe(200);
  expect(await publicationCommitResponse.json()).toMatchObject({
    id: publicationPreview.id,
    operation: "publish",
    status: "committed",
  });
  await page
    .getByRole("textbox", { name: "批次审核依据" })
    .fill(`Browser withdrawal correction ${testInfo.project.name}`);
  const withdrawalPreviewResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/governance/publication-batches/preview") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().operation === "withdraw",
  );
  await page.getByRole("button", { name: "基于此批次生成撤回预览" }).click();
  const withdrawalPreviewResponse = await withdrawalPreviewResponsePromise;
  expect(withdrawalPreviewResponse.status()).toBe(201);
  const withdrawalPreview = (await withdrawalPreviewResponse.json()) as {
    id: string;
    operation: string;
    blocked_count: number;
    status: string;
  };
  expect(withdrawalPreview).toMatchObject({
    operation: "withdraw",
    blocked_count: 0,
    status: "previewed",
  });
  const withdrawalCommitResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/publication-batches/${withdrawalPreview.id}/commit`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "原子提交撤回" }).click();
  const withdrawalCommitResponse = await withdrawalCommitResponsePromise;
  expect(withdrawalCommitResponse.status()).toBe(200);
  expect(await withdrawalCommitResponse.json()).toMatchObject({
    id: withdrawalPreview.id,
    operation: "withdraw",
    status: "committed",
  });
  await expect(page.getByText("检索投影维护", { exact: true })).toHaveCount(0);
  await expect(publicationFact).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return {
    ...context,
    governanceRunsResponse,
    publicationQuote,
    publicationFact,
    publicationPreviewResponsePromise,
    publicationPreviewResponse,
    publicationPreview,
    publicationCommitResponsePromise,
    publicationCommitResponse,
    withdrawalPreviewResponsePromise,
    withdrawalPreviewResponse,
    withdrawalPreview,
    withdrawalCommitResponsePromise,
    withdrawalCommitResponse,
  };
}
