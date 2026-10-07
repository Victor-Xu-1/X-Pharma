import { expect, type Page } from "@playwright/test";
import { openNavigation } from "../helpers";
import type { verifyIdentityAndQuality } from "./identity-and-quality";

async function expectTableResult(page: Page, column: string, emptyTitle: string) {
  const header = page.getByRole("columnheader", { name: column, exact: true });
  const empty = page.getByText(emptyTitle, { exact: true });
  // Either real rows or the explicit empty result must render, never a blank wide placeholder.
  await expect(header.or(empty)).toBeVisible();
  if (await empty.isVisible()) await expect(header).toHaveCount(0);
  else await expect(empty).toHaveCount(0);
}

export async function verifyCrossWorkbenchReturn(context: Awaited<ReturnType<typeof verifyIdentityAndQuality>>) {
  const { page, credentials, pipelineTargetId, fixtureKey } = context;
  await page.goto("/workspace/research?view=overview");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("research");
  await expect(page).toHaveURL(/\/workspace\/research/);
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await expect(page.getByLabel("邮箱", { exact: true })).toHaveValue(credentials.email);
  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}`);
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}`));
  await page.goBack();
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await page.goto("/workspace/research?view=knowledge");
  await expect(page.getByRole("heading", { name: "版本化知识专题" })).toBeVisible();

  await page.goto("/workspace/research?view=evidence");
  await expect(page.getByRole("heading", { name: "原始资料查证" })).toBeVisible();
  await page.getByPlaceholder("输入靶点、活性值、专利号、试验号或项目事实").fill(`No evidence ${fixtureKey}`);
  await page.getByRole("button", { name: "查证原文" }).click();
  await expect(page.getByText("未找到匹配证据", { exact: true })).toBeVisible();

  await page.goto("/workspace/internal");
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await openNavigation(page);
  await page.getByRole("button", { name: "商业运营" }).click();
  await expect(page.getByRole("heading", { name: "Agent 商业运营" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "合同与额度" })).toBeVisible();
  await page.getByRole("tab", { name: "导出策略" }).click();
  await expect(page.getByText("工作台导出策略", { exact: true })).toBeVisible();
  await expect(page.getByLabel("策略版本")).toBeVisible();
  await page.getByRole("tab", { name: "数据生命周期" }).click();
  await expect(page.getByRole("heading", { name: "导出对象保留策略" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "源资料保留策略" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "创建法律保全" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "法律保全记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "源资料撤回候选" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "已撤回源资料" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "到期导出对象" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "生命周期审计" })).toBeVisible();
  await page.getByRole("tab", { name: "Agent 客户端" }).click();
  await expectTableResult(page, "客户端", "暂无 Agent 客户端");
  await page.getByRole("tab", { name: "账单投递" }).click();
  await expect(page.getByRole("heading", { name: "计费账户映射" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Provider 投递队列" })).toBeVisible();
  await expectTableResult(page, "Provider 客户编号", "暂无计费账户");
  await page.getByLabel("投递状态").selectOption("dead");
  await expect(page.getByLabel("投递状态")).toHaveValue("dead");
  await expectTableResult(page, "最近错误", "暂无账单投递记录");
  await page.getByRole("tab", { name: "计费争议" }).click();
  await expect(page.getByRole("heading", { name: "计费争议案件" })).toBeVisible();
  await expect(page.getByLabel("争议状态")).toHaveValue("all");
  await expectTableResult(page, "争议额度", "暂无计费争议");
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
  return { ...context, hasOverflow };
}
