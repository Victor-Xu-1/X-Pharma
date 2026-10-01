import { expect } from "@playwright/test";
import type { verifyPipelineDossiers } from "./pipeline-dossiers";

export async function verifyRegulatoryAndDomainContinuity(context: Awaited<ReturnType<typeof verifyPipelineDossiers>>) {
  const {
    page,
    fixtureKeyBase,
    pipelineTargetId,
    pipelineOrganizationId,
    regulatorySubjectId,
    regulatoryIndicationId,
    regulatoryEventId,
    regulatoryNegativeEventId,
    patentFamilyId,
    newsEventId,
    dealEntityId,
    dealProfileId,
    regulatoryCompanyName,
  } = context;
  await page.goto(`/workspace/research?view=regulatory&q=${encodeURIComponent(fixtureKeyBase)}`);
  const regulatoryFilters = page.getByRole("form", { name: "监管事件筛选" });
  await expect(regulatoryFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await regulatoryFilters.getByLabel("监管机构").selectOption("FDA");
  await regulatoryFilters.getByLabel("辖区").selectOption("US");
  await regulatoryFilters.getByLabel("事件类型").selectOption("approval");
  await regulatoryFilters.getByLabel("认定资格").selectOption("breakthrough_therapy");
  await regulatoryFilters.getByText("更多监管与安全条件").click();
  await regulatoryFilters.getByLabel("事件状态").selectOption("approved");
  await regulatoryFilters.getByLabel("标签变更").selectOption("initial_label");
  await regulatoryFilters.getByLabel("黑框警告", { exact: true }).selectOption("true");
  await regulatoryFilters.getByLabel("安全信号", { exact: true }).selectOption("adverse_event");
  await regulatoryFilters.getByLabel("严重程度").selectOption("serious");
  await regulatoryFilters.getByLabel("信号状态").selectOption("confirmed");
  const regulatoryDecisionRange = regulatoryFilters.getByRole("group", { name: "决定日期" });
  await regulatoryDecisionRange.getByLabel("起").fill("2026-01-01");
  await regulatoryDecisionRange.getByLabel("止").fill("2026-12-31");
  const regulatorySourceRange = regulatoryFilters.getByRole("group", { name: "来源更新" });
  await regulatorySourceRange.getByLabel("起").fill("2026-01-01");
  await regulatorySourceRange.getByLabel("止").fill("2026-12-31");
  const regulatoryCorrectnessResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      url.searchParams.get("agency") === "FDA" &&
      url.searchParams.get("jurisdiction") === "US" &&
      url.searchParams.get("safety_status") === "confirmed"
    );
  });
  await regulatoryFilters.getByRole("button", { name: "查询", exact: true }).click();
  const regulatoryCorrectnessResponse = await regulatoryCorrectnessResponsePromise;
  const regulatoryCorrectnessPayload = (await regulatoryCorrectnessResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(regulatoryCorrectnessPayload.total).toBe(1);
  expect(regulatoryCorrectnessPayload.items.map((item) => item.id)).toEqual([regulatoryEventId]);
  expect(regulatoryCorrectnessPayload.items.some((item) => item.id === regulatoryNegativeEventId)).toBe(false);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-01-01/);
  await expect(page.getByRole("table", { name: "监管事件结果" })).toContainText(
    `Browser regulatory event ${fixtureKeyBase}`,
  );
  const regulatorySubscriptionName = `Browser regulatory subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const saveRegulatoryForm = page.getByRole("dialog", { name: "保存当前监管检索" });
  await saveRegulatoryForm.getByLabel("名称").fill(regulatorySubscriptionName);
  await saveRegulatoryForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("监管检索已保存并启用监控")).toBeVisible();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedRegulatoryRow = page.getByRole("row").filter({ hasText: regulatorySubscriptionName });
  await expect(savedRegulatoryRow).toContainText("监管与安全");
  await savedRegulatoryRow.getByRole("button", { name: `运行 ${regulatorySubscriptionName}` }).click();
  await expect(page).toHaveURL(/view=regulatory/);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-01-01/);
  await expect(page).toHaveURL(/decision_to=2026-12-31/);
  await expect(page).toHaveURL(/source_updated_from=2026-01-01/);
  await expect(page).toHaveURL(/source_updated_to=2026-12-31/);
  await page.reload();
  await expect(regulatoryFilters.getByLabel("认定资格")).toHaveValue("breakthrough_therapy");
  await expect(page.getByRole("table", { name: "监管事件结果" })).toContainText(
    `Browser regulatory event ${fixtureKeyBase}`,
  );
  await page.getByLabel(`选择对比 Browser regulatory event ${fixtureKeyBase}`).click();
  await expect(page).toHaveURL(/compare=[0-9a-f-]{36}/);
  await expect(page.getByText("已选 1/4 项", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "监管事件对比" })).toContainText("Interstitial lung disease");
  await page
    .getByRole("table", { name: "监管事件对比" })
    .getByRole("button", { name: `Browser regulatory drug ${fixtureKeyBase}` })
    .click();
  await expect(page).toHaveURL(/regulatory_event=[0-9a-f-]{36}/);
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Monitor pulmonary symptoms");
  await page.reload();
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await expect(regulatoryFilters.getByLabel("认定资格")).toHaveValue("breakthrough_therapy");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("dialog").getByRole("button", { name: "关闭监管事件详情" }).click();
  await page.getByRole("button", { name: "清除已选项" }).click();
  await expect(page).not.toHaveURL(/compare=/);
  await expect(page.getByRole("table", { name: "监管事件对比" })).toHaveCount(0);

  await page.goto(`/workspace/research?view=entity&entity=${regulatorySubjectId}&section=regulatory_events`);
  await expect(page.getByRole("heading", { name: `Browser regulatory drug ${fixtureKeyBase}` })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}.*section=regulatory`));
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");
  const approvedIndications = page.getByRole("table", { name: "药物获批适应症" });
  await expect(approvedIndications).toContainText(`Browser regulatory indication ${fixtureKeyBase}`);
  await expect(approvedIndications).toContainText("Adults with biomarker-positive disease");
  await expect(approvedIndications).toContainText("EGFR exon 20 insertion");
  await expect(approvedIndications).toContainText("美国");
  await expect(approvedIndications).toContainText("二线");
  await expect(approvedIndications).toContainText("口服");
  await expect(approvedIndications).toContainText("片剂");
  await approvedIndications
    .getByRole("button", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${regulatoryIndicationId}`));
  await expect(
    page.getByRole("heading", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开监管事件详情：Browser regulatory event ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=regulatory.*regulatory_event=${regulatoryEventId}`));
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "关闭监管事件详情" }).click();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}.*section=regulatory`));
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${pipelineOrganizationId}&section=programs`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}.*section=pipeline`));
  await expect(page.getByRole("heading", { name: regulatoryCompanyName, exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${dealEntityId}&section=deals`);
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: /打开交易详情/ }).click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*deal=${dealProfileId}`));
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await expect(page.getByText(/交易专业档案/)).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=entity&entity=${dealEntityId}.*section=deals`));
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}&section=patents`);
  await expect(page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByRole("tab", { name: "专利" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开专利族详情：WO-E2E-${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=patents.*patent=${patentFamilyId}`));
  await expect(page.getByRole("heading", { name: `Browser patent family ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByText(`专利族专业档案 · WO-E2E-${fixtureKeyBase}`)).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}.*section=patents`));
  await expect(page.getByRole("tab", { name: "专利" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}&section=news`);
  await expect(page.getByRole("tab", { name: "新闻与会议" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开新闻事件详情：Browser news event ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=news.*news_event=${newsEventId}`));
  const newsDialog = page.getByRole("dialog", { name: `Browser news event ${fixtureKeyBase}` });
  const closeNewsDialog = newsDialog.getByRole("button", { name: "关闭新闻事件详情" });
  await expect(closeNewsDialog).toBeFocused();
  const newsProvenanceTrigger = newsDialog.getByRole("button", {
    name: `查看 Browser news event ${fixtureKeyBase} 的原始证据`,
  });
  await newsProvenanceTrigger.click();
  const provenanceDialog = page.getByRole("dialog", { name: "原始证据" });
  return {
    ...context,
    regulatoryFilters,
    regulatoryDecisionRange,
    regulatorySourceRange,
    regulatoryCorrectnessResponsePromise,
    regulatoryCorrectnessResponse,
    regulatoryCorrectnessPayload,
    regulatorySubscriptionName,
    saveRegulatoryForm,
    savedRegulatoryRow,
    approvedIndications,
    newsDialog,
    closeNewsDialog,
    newsProvenanceTrigger,
    provenanceDialog,
  };
}
