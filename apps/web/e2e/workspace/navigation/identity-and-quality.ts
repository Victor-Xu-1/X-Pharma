import { expect } from "@playwright/test";
import type { verifyPublication } from "./publication";

export async function verifyIdentityAndQuality(context: Awaited<ReturnType<typeof verifyPublication>>) {
  const { page, testInfo, resolutionCaseId, qualityIssueId, qualityOwnerId, fixtureKey, governanceRunsResponse } =
    context;
  await page.getByRole("tab", { name: /实体消歧/ }).click();
  await page.getByRole("tab", { name: /历史与回滚/ }).click();
  const resolutionSourceName = `Browser resolution alias ${testInfo.project.name}`;
  const resolutionCaseRow = page.getByRole("button").filter({ hasText: resolutionSourceName });
  await expect(resolutionCaseRow).toBeVisible();
  await resolutionCaseRow.click();
  await expect(page.getByRole("heading", { name: "跨域影响分析" })).toBeVisible();
  await expect(page.getByText("target_profiles.entity_id", { exact: true })).toBeVisible();
  await expect(page.getByText("不可变决策历史", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "拆分恢复依据" }).fill(`Browser rollback ${testInfo.project.name}`);
  const rollbackResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/entity-resolution-cases/${resolutionCaseId}/decision`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "拆分并恢复独立实体" }).click();
  const rollbackResponse = await rollbackResponsePromise;
  expect(rollbackResponse.status()).toBe(200);
  expect(await rollbackResponse.json()).toMatchObject({ id: resolutionCaseId, status: "reverted" });
  await expect(page.getByText("拆分恢复", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("tab", { name: "质量运营" }).click();
  await expect(page.getByRole("heading", { name: "数据质量运营" })).toBeVisible();
  await expect(page.locator(".quality-metric-grid article")).toHaveCount(6);
  await expect(page.getByRole("heading", { name: "最近 12 次趋势" })).toBeVisible();
  const qualityIssueTitle = `Browser quality issue ${fixtureKey}`;
  const qualityIssue = page.locator(".quality-issue-list button").filter({ hasText: qualityIssueTitle });
  await expect(qualityIssue).toBeVisible();
  await qualityIssue.click();
  await expect(page.getByRole("heading", { name: qualityIssueTitle })).toBeVisible();
  await page.getByLabel("负责人").selectOption(qualityOwnerId);
  const assignmentResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/quality/issues/${qualityIssueId}/actions`) &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().action === "assign",
  );
  await page.getByRole("button", { name: "分配", exact: true }).click();
  const assignmentResponse = await assignmentResponsePromise;
  expect(assignmentResponse.status()).toBe(200);
  expect(await assignmentResponse.json()).toMatchObject({
    id: qualityIssueId,
    owner_user_id: qualityOwnerId,
    status: "open",
  });
  const acknowledgeResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/quality/issues/${qualityIssueId}/actions`) &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().action === "acknowledge",
  );
  await page.getByRole("button", { name: "确认接手", exact: true }).click();
  const acknowledgeResponse = await acknowledgeResponsePromise;
  expect(acknowledgeResponse.status()).toBe(200);
  expect(await acknowledgeResponse.json()).toMatchObject({ id: qualityIssueId, status: "acknowledged" });
  await expect(page.locator(".quality-event-history")).toContainText("assign");
  await expect(page.locator(".quality-event-history")).toContainText("acknowledge");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("tab", { name: "运行追踪" }).click();
  expect((await governanceRunsResponse).status()).toBe(200);
  await expect(page.getByLabel("运行状态")).toBeVisible();
  await expect(page.getByText(/共 \d+ 次运行/)).toBeVisible();
  const overflowingElements = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    return Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const bounds = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          className: element.className,
          left: Math.round(bounds.left),
          right: Math.round(bounds.right),
          width: Math.round(bounds.width),
        };
      })
      .filter(({ right }) => right > viewportWidth + 1)
      .slice(0, 20);
  });
  expect(overflowingElements).toEqual([]);
  return {
    ...context,
    resolutionSourceName,
    resolutionCaseRow,
    rollbackResponsePromise,
    rollbackResponse,
    qualityIssueTitle,
    qualityIssue,
    assignmentResponsePromise,
    assignmentResponse,
    acknowledgeResponsePromise,
    acknowledgeResponse,
    overflowingElements,
  };
}
