import { expect } from "@playwright/test";
import type { verifyNewsDealAndPatentDetails } from "./news-deal-and-patent-details";

export async function verifyDealRegulatoryAndSavedSearch(
  context: Awaited<ReturnType<typeof verifyNewsDealAndPatentDetails>>,
) {
  const {
    page,
    fixtureKeyBase,
    pipelineTargetId,
    pipelineCombinationTargetId,
    pipelineDiseaseId,
    companyName,
    createdCompany,
  } = context;
  await page.goto("/workspace/research?view=deals&q=license");
  const dealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(dealFilters.getByLabel("关键词")).toHaveValue("license");
  await dealFilters.getByLabel("交易状态").selectOption("active");
  await dealFilters.getByLabel("交易方向").selectOption("outbound");
  await dealFilters.getByLabel("参与机构").fill(companyName);
  await page
    .getByRole("option")
    .filter({ has: page.getByText(companyName, { exact: true }) })
    .click();
  await dealFilters.getByLabel("参与角色").selectOption("licensor");
  await dealFilters.getByText("更多交易条件").click();
  await dealFilters.getByLabel("方向参照地区").fill("US");
  await dealFilters.getByLabel("机构所在地区").fill("US");
  await dealFilters.getByLabel("机构类型").fill("biopharma");
  await dealFilters.getByLabel("交易时阶段").selectOption("phase_2");
  await dealFilters.getByLabel("当前最高阶段").selectOption("phase_3");
  await dealFilters.getByLabel("权益类型").selectOption("commercialization");
  const announcedRange = dealFilters.getByRole("group", { name: "初始披露" });
  await announcedRange.getByLabel("起").fill("2026-01-01");
  await announcedRange.getByLabel("止").fill("2026-12-31");
  const terminatedRange = dealFilters.getByRole("group", { name: "终止日期" });
  await terminatedRange.getByLabel("起").fill("2026-02-01");
  await terminatedRange.getByLabel("止").fill("2026-12-31");
  const updatedRange = dealFilters.getByRole("group", { name: "信息更新" });
  await updatedRange.getByLabel("起").fill("2026-03-01");
  await updatedRange.getByLabel("止").fill("2026-12-31");
  const upfrontRange = dealFilters.getByRole("group", { name: "首付款" });
  await upfrontRange.getByLabel("下限").fill("10000000");
  await upfrontRange.getByLabel("上限").fill("30000000");
  const totalRange = dealFilters.getByRole("group", { name: "潜在总额" });
  await totalRange.getByLabel("下限").fill("100000000");
  await totalRange.getByLabel("上限").fill("500000000");
  await dealFilters.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/status=active/);
  await expect(page).toHaveURL(/direction=outbound/);
  await expect(page).toHaveURL(/direction_reference_jurisdiction=US/);
  await expect(page).toHaveURL(new RegExp(`party_entity_id=${createdCompany.id}`));
  await expect(page).toHaveURL(/party_role=licensor/);
  await expect(page).toHaveURL(/party_country_region=US/);
  await expect(page).toHaveURL(/party_organization_type=biopharma/);
  await expect(page).toHaveURL(/development_phase_at_transaction=phase_2/);
  await expect(page).toHaveURL(/current_development_phase=phase_3/);
  await expect(page).toHaveURL(/right_type=commercialization/);
  await expect(page).toHaveURL(/announced_from=2026-01-01/);
  await expect(page).toHaveURL(/terminated_from=2026-02-01/);
  await expect(page).toHaveURL(/source_updated_from=2026-03-01/);
  await expect(page).toHaveURL(/upfront_amount_min=10000000/);
  await expect(page).toHaveURL(/total_potential_amount_max=500000000/);
  const appliedDealFilters = page.getByRole("region", { name: "已应用查询条件" });
  await expect(appliedDealFilters).toContainText("active");
  await expect(appliedDealFilters).toContainText("licensor");
  await expect(appliedDealFilters).toContainText("phase_2");
  await page.reload();
  await expect(dealFilters.getByLabel("交易状态")).toHaveValue("active");
  await expect(dealFilters.getByLabel("交易方向")).toHaveValue("outbound");
  await expect(dealFilters.getByLabel("参与机构")).toHaveValue(companyName);
  await expect(dealFilters.getByLabel("参与角色")).toHaveValue("licensor");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  const pipelineFilters = page.getByRole("form", { name: "药物与管线筛选" });
  await expect(pipelineFilters.getByRole("group", { name: "靶点检索与选择" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(pipelineFilters.getByRole("group", { name: "适应症检索与选择" })).toContainText(
    `Browser regulatory indication ${fixtureKeyBase}`,
  );
  const pipelineLandscape = page.getByLabel("管线竞争格局");
  await expect(page.getByRole("button", { name: "格局" })).toHaveAttribute("aria-pressed", "true");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("3");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^药物$/ })
      .locator(".."),
  ).toContainText("3");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发机构$/ })
      .locator(".."),
  ).toContainText("2");
  await expect(pipelineLandscape.getByRole("img", { name: "药物类型项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "靶点项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "靶点组合项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "适应症项目数量分布" })).toBeVisible();
  await expect(page.getByText("导出", { exact: true })).toBeVisible();
  await expect(
    pipelineLandscape.getByRole("button", { name: `打开Browser regulatory company ${fixtureKeyBase}档案` }),
  ).toBeVisible();
  const analysisControls = pipelineLandscape.getByRole("group", { name: "竞争格局分析控制" });
  await analysisControls.getByLabel("分析维度").selectOption("targets");
  await expect(page).toHaveURL(/analysis_dimension=targets/);
  await analysisControls.getByRole("button", { name: "表格" }).click();
  await expect(page).toHaveURL(/analysis_view=table/);
  await analysisControls.getByLabel("分析显示范围").selectOption("50");
  await expect(page).toHaveURL(/analysis_top=50/);
  await analysisControls.getByLabel("阶段分析口径").selectOption("global");
  await expect(page).toHaveURL(/analysis_stage=global/);
  await analysisControls.getByLabel("靶点聚合口径").selectOption("primary");
  await expect(page).toHaveURL(/target_aggregation=primary/);
  await expect(pipelineLandscape.getByRole("table", { name: "靶点统计表" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("columnheader", { name: "阶段构成" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("heading", { name: "适应症", exact: true })).toHaveCount(0);
  const pipelineSubscriptionName = `Browser pipeline subscription ${fixtureKeyBase}`;
  const savePipelineTrigger = page.getByRole("button", { name: "保存/订阅" });
  await savePipelineTrigger.click();
  const savePipelineDialog = page.getByRole("dialog", { name: "保存当前管线检索" });
  const savePipelineName = savePipelineDialog.getByLabel("名称");
  await expect(savePipelineName).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(savePipelineDialog).toHaveCount(0);
  await expect(savePipelineTrigger).toBeFocused();
  await savePipelineTrigger.click();
  await expect(savePipelineName).toBeFocused();
  await savePipelineName.fill(pipelineSubscriptionName);
  await savePipelineDialog.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("管线检索已保存并启用监控")).toBeVisible();
  await expect(savePipelineTrigger).toBeFocused();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedPipelineRow = page.getByRole("row").filter({ hasText: pipelineSubscriptionName });
  await expect(savedPipelineRow).toContainText("药物与管线");
  await expect(savedPipelineRow).toContainText("统计表");
  await expect(savedPipelineRow).toContainText("条件：靶点=已选");
  const editSavedPipelineTrigger = savedPipelineRow.getByRole("button", { name: `编辑 ${pipelineSubscriptionName}` });
  await editSavedPipelineTrigger.click();
  const savedSearchEditor = page.getByRole("dialog", { name: "编辑已保存检索" });
  const maintainedPipelineSubscriptionName = `${pipelineSubscriptionName} curated`;
  const savedSearchName = savedSearchEditor.getByLabel("名称");
  await expect(savedSearchName).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(savedSearchEditor).toHaveCount(0);
  await expect(editSavedPipelineTrigger).toBeFocused();
  await editSavedPipelineTrigger.click();
  await expect(savedSearchName).toBeFocused();
  await savedSearchName.fill(maintainedPipelineSubscriptionName);
  await savedSearchEditor.getByLabel("业务说明").fill("季度竞争格局复核口径");
  await savedSearchEditor.getByRole("button", { name: "保存修改" }).click();
  await expect(savedSearchEditor).toHaveCount(0);
  const maintainedPipelineRow = page.getByRole("row").filter({ hasText: maintainedPipelineSubscriptionName });
  await expect(maintainedPipelineRow).toContainText("季度竞争格局复核口径");
  await expect(maintainedPipelineRow).toContainText("v1");
  await maintainedPipelineRow.getByRole("button", { name: `运行 ${maintainedPipelineSubscriptionName}` }).click();
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/analysis_dimension=targets/);
  await expect(page).toHaveURL(/analysis_view=table/);
  await expect(page).toHaveURL(/analysis_top=50/);
  await expect(page).toHaveURL(/analysis_stage=global/);
  await expect(page).toHaveURL(/target_aggregation=primary/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  await expect(page).not.toHaveURL(/analysis_/);
  const targetCombinationDistribution = pipelineLandscape
    .locator(".pipeline-landscape-distribution")
    .filter({ has: page.getByRole("heading", { name: "靶点组合", exact: true }) });
  const dualTargetCombination = targetCombinationDistribution
    .locator("li")
    .filter({ hasText: `Browser combination target ${fixtureKeyBase}` });
  await expect(dualTargetCombination).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await dualTargetCombination.getByRole("button").click();
  await expect(page).toHaveURL(new RegExp(`target_combination_key=.*${pipelineCombinationTargetId}`));
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("1");
  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  await pipelineLandscape.getByTitle("按抗体筛选", { exact: true }).click();
  await expect(page).toHaveURL(/modality=antibody/);
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("1");
  await page.reload();
  await expect(page.getByRole("button", { name: "格局" })).toHaveAttribute("aria-pressed", "true");
  await pipelineFilters.getByLabel(/药物类型：/).click();
  await expect(pipelineFilters.getByRole("checkbox", { name: /^抗体\s*\d+$/ })).toBeChecked();
  return {
    ...context,
    dealFilters,
    announcedRange,
    terminatedRange,
    updatedRange,
    upfrontRange,
    totalRange,
    appliedDealFilters,
    pipelineFilters,
    pipelineLandscape,
    analysisControls,
    pipelineSubscriptionName,
    savePipelineTrigger,
    savePipelineDialog,
    savePipelineName,
    savedPipelineRow,
    editSavedPipelineTrigger,
    savedSearchEditor,
    maintainedPipelineSubscriptionName,
    savedSearchName,
    maintainedPipelineRow,
    targetCombinationDistribution,
    dualTargetCombination,
  };
}
