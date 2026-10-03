import { expect } from "@playwright/test";
import { findDataFactoryRunRow, findSourceAssetRow, openNavigation } from "../helpers";
import type { verifyRegulatoryAndDomainContinuity } from "./regulatory-and-domain-continuity";

export async function verifyIngestionAndQuarantine(
  context: Awaited<ReturnType<typeof verifyRegulatoryAndDomainContinuity>>,
) {
  const {
    page,
    testInfo,
    fixtureKeyBase,
    pipelineTargetId,
    ingestionRunId,
    quarantineVersionId,
    companyName,
    createdCompany,
    newsDialog,
    newsProvenanceTrigger,
    provenanceDialog,
  } = context;
  await expect(provenanceDialog.getByRole("button", { name: "关闭原始证据" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(provenanceDialog).toHaveCount(0);
  await expect(newsDialog).toBeVisible();
  await expect(newsProvenanceTrigger).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(newsDialog).toHaveCount(0);
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}.*section=news`));
  await expect(page.getByRole("tab", { name: "新闻与会议" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${createdCompany.id}`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${createdCompany.id}`));
  await expect(page.getByRole("heading", { name: companyName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "研发管线" }).click();
  await expect(page.getByText("暂无关联研发管线", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await expect(page.getByText("暂无带日期的公司事件", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto("/workspace/internal");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await expect(page.getByRole("heading", { name: "自动数据工厂" })).toBeVisible();
  await openNavigation(page);
  const internalNavigation = page.getByRole("navigation", { name: "主导航" });
  for (const researchView of [
    "用户中心",
    "情报检索",
    "结构检索",
    "靶点全景",
    "原始证据",
    "知识专题",
    "监控与提醒",
    "对比与列表",
  ]) {
    await expect(internalNavigation.getByRole("button", { name: researchView, exact: true })).toHaveCount(0);
  }
  await page.getByRole("button", { name: "数据工厂", exact: true }).click();
  await expect(page.getByRole("heading", { name: "自动数据工厂" })).toBeVisible();
  const quarantineFile = `browser-quarantine-${testInfo.project.name}.md`;
  const quarantineRow = page.getByRole("row").filter({ hasText: quarantineFile });
  await expect(quarantineRow.getByText("Win.Test.EICAR_HDB-1")).toBeVisible();
  await quarantineRow.getByRole("button", { name: "处置" }).click();
  const quarantineDialog = page.getByRole("dialog", { name: "隔离案件处置" });
  await expect(quarantineDialog).toBeVisible();
  await expect(quarantineDialog.getByText(/仍强制经过 ClamAV/)).toBeVisible();
  await expect(quarantineDialog.getByText("扫描发现威胁")).toBeVisible();
  await expect(quarantineDialog.getByLabel("处置动作")).toHaveValue("hold");
  await quarantineDialog.getByLabel("处置原因").fill(`Browser security hold ${testInfo.project.name}`);
  const quarantineResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/admin/quarantine-cases/${quarantineVersionId}/decisions`) &&
      response.request().method() === "POST",
  );
  await quarantineDialog.getByRole("button", { name: "提交处置" }).click();
  const quarantineResponse = await quarantineResponsePromise;
  expect(quarantineResponse.status()).toBe(200);
  expect(await quarantineResponse.json()).toMatchObject({
    source_version_id: quarantineVersionId,
    action: "hold",
    quarantine_status: "held",
    quarantine_version: 2,
  });
  await expect(quarantineDialog.getByText("处置已记录：留置待审")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  const closeQuarantine = quarantineDialog.getByRole("button", { name: "关闭隔离案件" });
  await expect(closeQuarantine).toBeEnabled();
  await closeQuarantine.click();
  const replayWorkflow = `browser-replay-${fixtureKeyBase}-${testInfo.project.name}`;
  const replayRow = await findDataFactoryRunRow(page, replayWorkflow);
  await replayRow.getByRole("button", { name: "运行详情" }).click();
  await expect(page.getByRole("heading", { name: "逐阶段运行图" })).toBeVisible();
  await expect(page.getByText("发现", { exact: true })).toBeVisible();
  await expect(page.getByText("安全扫描", { exact: true })).toBeVisible();
  await expect(page.getByText("AI 治理", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  const recoveryFile = `browser-recovery-${testInfo.project.name}.md`;
  const recoveryAssetRow = await findSourceAssetRow(page, recoveryFile);
  await recoveryAssetRow.getByRole("button", { name: `查看 ${recoveryFile} 版本` }).click();
  const sourceAssetDialog = page.getByRole("dialog", { name: recoveryFile });
  await expect(sourceAssetDialog).toBeVisible();
  await page.getByRole("button", { name: "选择恢复阶段" }).click();
  const stageReplayDialog = page.getByRole("dialog", { name: "重放源版本 1" });
  await expect(stageReplayDialog.getByLabel("恢复起点")).toHaveValue("parse");
  await expect(stageReplayDialog.getByRole("option", { name: "安全扫描" })).toHaveCount(1);
  await expect(stageReplayDialog.getByRole("option", { name: "文档解析" })).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await stageReplayDialog.getByRole("button", { name: "关闭" }).click();
  await sourceAssetDialog.getByRole("button", { name: "关闭源对象详情" }).click();
  const replayResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/admin/ingestion-runs/${ingestionRunId}/replay`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: `重放 ${replayWorkflow}` }).click();
  await page.getByLabel("重放原因").fill(`Browser recovery ${testInfo.project.name}`);
  await page.getByRole("button", { name: "确认重放" }).click();
  const replayResponse = await replayResponsePromise;
  expect(replayResponse.status()).toBe(202);
  await expect(page.getByRole("dialog", { name: "重放入库运行" })).toHaveCount(0);
  await page.getByRole("button", { name: "接入自动数据源" }).click();
  await expect(page.getByLabel("授权生效时间")).toBeVisible();
  await expect(page.getByLabel("授权结束时间（留空表示长期有效）")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("http_manifest");
  await expect(page.getByLabel("Manifest API 地址")).toBeVisible();
  await expect(page.getByLabel("凭据引用")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("s3_snapshot");
  await expect(page.getByLabel("S3 Bucket / Prefix")).toHaveValue("s3://licensed-supplier/research/");
  await expect(page.getByPlaceholder("env://SUPPLIER_S3_CREDENTIALS_JSON")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("sftp_snapshot");
  await expect(page.getByLabel("SFTP 目录地址")).toHaveValue("sftp://supplier.example:22/delivery/");
  await expect(page.getByPlaceholder("env://SUPPLIER_SFTP_CREDENTIALS_JSON")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("smb_snapshot");
  await expect(page.getByLabel("SMB 共享目录地址")).toHaveValue("smb://fileserver.example:445/research/delivery/");
  await expect(page.getByPlaceholder("env://ENTERPRISE_SMB_CREDENTIALS_JSON")).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  return {
    ...context,
    internalNavigation,
    quarantineFile,
    quarantineRow,
    quarantineDialog,
    quarantineResponsePromise,
    quarantineResponse,
    closeQuarantine,
    replayWorkflow,
    replayRow,
    recoveryFile,
    recoveryAssetRow,
    sourceAssetDialog,
    stageReplayDialog,
    replayResponsePromise,
    replayResponse,
  };
}
