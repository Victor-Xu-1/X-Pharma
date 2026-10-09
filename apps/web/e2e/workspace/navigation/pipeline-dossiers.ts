import { expect } from "@playwright/test";
import { trialInitiationTypeLabels } from "../../../src/lib/trialFilters";
import { verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyDealRegulatoryAndSavedSearch } from "./deal-regulatory-and-saved-search";

export async function verifyPipelineDossiers(context: Awaited<ReturnType<typeof verifyDealRegulatoryAndSavedSearch>>) {
  const {
    page,
    fixtureKeyBase,
    pipelineTargetId,
    pipelineDiseaseId,
    trialProfileId,
    pipelineOrganizationId,
    pipelineCollaboratorId,
    regulatorySubjectId,
    regulatoryIndicationId,
    dealProfileId,
    pipelineFilters,
  } = context;
  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&organization_entity_id=${pipelineCollaboratorId}`,
  );
  await expect(pipelineFilters.getByRole("group", { name: "研发机构检索与选择" })).toContainText(
    `Browser pipeline company B ${fixtureKeyBase}`,
  );
  await pipelineFilters.getByText("机构、区域阶段、权益与里程碑").click();
  await pipelineFilters.getByLabel("机构角色").selectOption("collaborator");
  await pipelineFilters.getByLabel("机构类型").selectOption("biotech");
  await pipelineFilters.getByLabel("机构所在地区").selectOption("US");
  await pipelineFilters.getByLabel("全球最高阶段").selectOption("phase_2");
  await pipelineFilters.getByLabel("中国最高阶段").selectOption("phase_1");
  await pipelineFilters.getByLabel("研发权益地区").selectOption("Global");
  await pipelineFilters.getByLabel("商业化权益地区").selectOption("Greater China");
  await pipelineFilters.getByLabel(/项目标签：/).click();
  await pipelineFilters.getByRole("checkbox", { name: /First-in-Class/ }).click();
  await pipelineFilters.getByLabel("里程碑类型").selectOption("first_patient_in");
  const milestoneRange = pipelineFilters.getByRole("group", { name: "里程碑日期" });
  await milestoneRange.getByLabel("起").fill("2026-06-01");
  await milestoneRange.getByLabel("止").fill("2026-06-30");
  await pipelineFilters.getByText("临床结果与交易信号").click();
  await pipelineFilters.getByLabel("是否已有临床结果").selectOption("true");
  await pipelineFilters.getByLabel("临床结果评价").selectOption("positive");
  await pipelineFilters.getByLabel("是否存在交易记录").selectOption("true");
  await pipelineFilters.getByLabel("交易币种").selectOption("USD");
  await pipelineFilters.getByLabel("潜在总额下限").fill("400000000");
  await pipelineFilters.getByLabel("潜在总额上限").fill("600000000");
  const exactOrganizationRelationshipResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      url.searchParams.get("organization_entity_id") === pipelineCollaboratorId &&
      url.searchParams.get("organization_role") === "collaborator" &&
      url.searchParams.get("organization_type") === "biotech" &&
      url.searchParams.get("organization_country_region") === "US"
    );
  });
  await pipelineFilters.getByRole("button", { name: "查询", exact: true }).click();
  const exactOrganizationRelationship = await exactOrganizationRelationshipResponse;
  expect(exactOrganizationRelationship.ok()).toBe(true);
  const exactOrganizationPayload = (await exactOrganizationRelationship.json()) as {
    total: number;
    items: Array<{ drug_entity_id: string }>;
  };
  expect(exactOrganizationPayload.total).toBe(1);
  expect(exactOrganizationPayload.items.map((item) => item.drug_entity_id)).toEqual([regulatorySubjectId]);
  await expect(page).toHaveURL(/global_phase=phase_2/);
  await expect(page).toHaveURL(/organization_role=collaborator/);
  await expect(page).toHaveURL(/organization_type=biotech/);
  await expect(page).toHaveURL(/organization_country_region=US/);
  await expect(page).toHaveURL(/china_phase=phase_1/);
  await expect(page).toHaveURL(/commercialization_rights_region=Greater\+China/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);
  await expect(page).toHaveURL(/milestone_from=2026-06-01/);
  await expect(page).toHaveURL(/has_clinical_results=true/);
  await expect(page).toHaveURL(/clinical_result_evaluation=positive/);
  await expect(page).toHaveURL(/has_deal=true/);
  await expect(page).toHaveURL(/deal_currency=USD/);
  await expect(page).toHaveURL(/deal_total_potential_amount_min=400000000/);
  const pipelineResultsUrl = new URL(page.url());
  const pipelineTable = page.getByRole("table", { name: "药物与研发管线结果" });
  await expect(pipelineTable).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText("合作方");
  await expect(pipelineTable).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText("2 项试验");
  await expect(pipelineTable).toContainText("积极");
  await expect(pipelineTable).toContainText("1 笔交易");
  await expect(pipelineTable).toContainText("USD");
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/pipelines",
    resultSurface: pipelineTable,
  });
  await expect(pipelineTable.getByRole("columnheader", { name: /作用机制/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /总体阶段/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /项目状态/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /全球阶段起始/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /中国阶段起始/ })).toBeVisible();
  await expect(pipelineTable).toContainText("covalent inhibitor");
  await expect(pipelineTable).toContainText("进行中");
  await expect(pipelineTable).toContainText("2026/06/01");
  await expect(pipelineTable).toContainText("2025/03/01");
  const pipelineResearchUrl = page.url();
  await pipelineTable
    .getByRole("button", { name: `查看 Browser regulatory drug ${fixtureKeyBase} 的 2 项临床试验` })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=trials.*role_entity_id=${regulatorySubjectId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("关联药物");
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.goBack();
  await expect(page).toHaveURL(pipelineResearchUrl);
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await page
    .getByRole("table", { name: "药物与研发管线结果" })
    .getByRole("button", { name: `查看 Browser regulatory drug ${fixtureKeyBase} 的 1 笔交易` })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*asset_entity_id=${regulatorySubjectId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("交易药品");
  await expect(page.getByRole("table", { name: "交易结果" })).toContainText(`Browser deal ${fixtureKeyBase}`);
  await page.goBack();
  await expect(page).toHaveURL(pipelineResearchUrl);
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(page.getByText(/全部结果按状态日期降序/)).toBeVisible();
  const sortedPipelineResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["mechanism_of_action:asc", "drug_name:desc"])
    );
  });
  const pipelineSortMenu = page.locator(".table-sort-menu");
  await pipelineSortMenu.getByText("排序", { exact: true }).click();
  await expect(pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true })).toHaveValue("status_date");
  await pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true }).selectOption("mechanism_of_action");
  await pipelineSortMenu.getByRole("button", { name: "第 1 排序方向：升序" }).click();
  await pipelineSortMenu.getByRole("button", { name: "添加排序字段" }).click();
  await pipelineSortMenu.getByLabel("第 2 排序字段", { exact: true }).selectOption("drug_name");
  await pipelineSortMenu.getByRole("button", { name: "第 2 排序方向：降序" }).click();
  expect(new URL(page.url()).searchParams.getAll("sort")).toEqual([]);
  await pipelineSortMenu.getByRole("button", { name: "应用排序" }).click();
  const pipelineSortResponse = await sortedPipelineResponse;
  expect(pipelineSortResponse.ok()).toBe(true);
  const pipelineSortPayload = (await pipelineSortResponse.json()) as {
    sort_by: string;
    sort_direction: string;
    sort: Array<{ field: string; direction: string }>;
  };
  expect(pipelineSortPayload).toMatchObject({
    sort_by: "mechanism_of_action",
    sort_direction: "asc",
    sort: [
      { field: "mechanism_of_action", direction: "asc" },
      { field: "drug_name", direction: "desc" },
    ],
  });
  expect(new URL(page.url()).searchParams.getAll("sort")).toEqual(["mechanism_of_action:asc", "drug_name:desc"]);
  await expect(page.getByText(/全部结果按作用机制升序、药物降序/)).toBeVisible();
  await page.reload();
  await expect(pipelineFilters.getByLabel("是否已有临床结果")).toHaveValue("true");
  await expect(pipelineFilters.getByLabel("临床结果评价")).toHaveValue("positive");
  await expect(pipelineFilters.getByLabel("是否存在交易记录")).toHaveValue("true");
  await expect(pipelineFilters.getByLabel("交易币种")).toHaveValue("USD");
  await expect(pipelineFilters.getByLabel("机构角色")).toHaveValue("collaborator");
  await expect(pipelineFilters.getByLabel("机构类型")).toHaveValue("biotech");
  await expect(pipelineFilters.getByLabel("机构所在地区")).toHaveValue("US");
  await pipelineSortMenu.getByText("排序", { exact: true }).click();
  await expect(pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true })).toHaveValue("mechanism_of_action");
  await expect(pipelineSortMenu.getByRole("button", { name: "第 1 排序方向：升序" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(pipelineSortMenu.getByLabel("第 2 排序字段", { exact: true })).toHaveValue("drug_name");
  await expect(pipelineSortMenu.getByRole("button", { name: "第 2 排序方向：降序" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(pipelineTable.getByRole("columnheader", { name: /作用机制/ })).toHaveAttribute("aria-sort", "ascending");
  await expect(pipelineTable.getByRole("columnheader", { name: /药物/ }).locator(".sort-priority")).toHaveText("2");
  const pipelineColumnMenu = page.locator(".table-column-menu");
  await pipelineColumnMenu.locator("summary").click();
  await pipelineColumnMenu.getByRole("checkbox", { name: "显示列：记录地区" }).uncheck();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toHaveCount(0);
  await page.reload();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toHaveCount(0);
  await pipelineColumnMenu.locator("summary").click();
  await pipelineColumnMenu.getByRole("checkbox", { name: "显示列：记录地区" }).check();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toBeVisible();
  const pipelineViewport = page.getByRole("region", { name: "药物与研发管线结果滚动区域" });
  await pipelineViewport.evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  const stickyIdentityColumn = await pipelineViewport.evaluate((element) => {
    const firstCell = element.querySelector<HTMLElement>(".virtual-table-cell:first-child");
    if (!firstCell) return null;
    const viewportRect = element.getBoundingClientRect();
    const cellRect = firstCell.getBoundingClientRect();
    return {
      cellLeft: Math.round(cellRect.left),
      viewportLeft: Math.round(viewportRect.left),
      overflow: element.scrollWidth > element.clientWidth,
    };
  });
  expect(stickyIdentityColumn).not.toBeNull();
  expect(
    Math.abs((stickyIdentityColumn?.cellLeft ?? 0) - (stickyIdentityColumn?.viewportLeft ?? 0)),
  ).toBeLessThanOrEqual(2);
  await page.reload();
  await expect(pipelineFilters.getByLabel("里程碑类型")).toHaveValue("first_patient_in");
  await expect(pipelineTable).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  const regulatoryDrugName = `Browser regulatory drug ${fixtureKeyBase}`;
  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: new RegExp(`^${regulatoryDrugName}`) }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await expect(page.getByRole("heading", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await expect(
    page
      .locator("dt")
      .filter({ hasText: /^全球 \/ 中国$/ })
      .locator(".."),
  ).toContainText("II 期临床 / I 期临床");
  await expect(page.getByRole("button", { name: `Browser pipeline target ${fixtureKeyBase}` })).toBeVisible();
  await page.locator(".drug-profile-structure").scrollIntoViewIfNeeded();
  await expect(page.getByRole("img", { name: `${regulatoryDrugName} 2D 结构` })).toBeVisible();
  await page.getByRole("tab", { name: "研发管线" }).click();
  await expect(page).toHaveURL(/section=pipeline/);
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  const drugProgramProgress = page.getByRole("table", { name: "药物适应症与地区进度" });
  await expect(drugProgramProgress).toContainText(`Browser regulatory indication ${fixtureKeyBase}`);
  await expect(drugProgramProgress).toContainText("II 期临床");
  await expect(drugProgramProgress).toContainText("I 期临床");
  await expect(drugProgramProgress).toContainText("在研");
  await expect(drugProgramProgress).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  const drugProgramRights = page.getByRole("table", { name: "药物研发机构与权益" });
  await expect(drugProgramRights).toContainText(`Browser regulatory company ${fixtureKeyBase}`);
  await expect(drugProgramRights).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugProgramRights).toContainText("原研 · 中国 · biopharma");
  await expect(drugProgramRights).toContainText("合作研发 · 美国 · biotech");
  await expect(drugProgramRights).toContainText("全球");
  await expect(drugProgramRights).toContainText("大中华区");
  await expect(drugProgramRights).toContainText("First-in-Class");
  await expect(drugProgramRights).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  await drugProgramProgress
    .getByRole("button", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${regulatoryIndicationId}`));
  await expect(
    page.getByRole("heading", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "临床结果与试验" }).click();
  await expect(page).toHaveURL(/section=trials/);
  const drugClinicalResults = page.getByRole("table", { name: "药物临床结果" });
  await expect(drugClinicalResults).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await expect(drugClinicalResults).toContainText("Objective response rate");
  await expect(drugClinicalResults).toContainText("Cohort A: 42 %");
  await expect(drugClinicalResults).toContainText("积极");
  await expect(drugClinicalResults).toContainText("一线");
  await expect(drugClinicalResults).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(drugClinicalResults).toContainText(`Browser combination target ${fixtureKeyBase}`);
  const drugClinicalTrials = page.getByRole("table", { name: "药物关联临床试验" });
  await expect(drugClinicalTrials).toContainText("招募中");
  await expect(drugClinicalTrials).toContainText(trialInitiationTypeLabels.ist);
  await expect(drugClinicalTrials).toContainText(`Browser intervention ${fixtureKeyBase}`);
  await expect(drugClinicalTrials).toContainText(`Browser sponsor ${fixtureKeyBase}`);
  await expect(drugClinicalTrials).toContainText("128");
  await drugClinicalResults
    .getByRole("button", { name: `打开临床试验详情：NCT-E2E-${fixtureKeyBase}` })
    .first()
    .click();
  await expect(page).toHaveURL(new RegExp(`view=trials.*trial=${trialProfileId}`));
  await expect(
    page.getByRole("heading", { name: `Browser clinical trial ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "临床结果与试验" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "交易" }).click();
  await expect(page).toHaveURL(/section=deals/);
  const drugDeals = page.getByRole("table", { name: "药物关联交易" });
  await expect(drugDeals).toContainText(`Browser deal ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("许可");
  await expect(drugDeals).toContainText("进行中");
  await expect(drugDeals).toContainText("对外许可");
  await expect(drugDeals).toContainText(`Browser regulatory company ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("许可方 · 美国 · biopharma");
  await expect(drugDeals).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("被许可方 · 中国 · biotech");
  await expect(drugDeals).toContainText("交易时 I 期临床 · 当前 II 期临床");
  await expect(drugDeals).toContainText("首付款 USD 25.0M");
  await expect(drugDeals).toContainText("潜在总额 USD 500.0M");
  const drugDealRights = page.getByRole("table", { name: "药物交易权益归属" });
  await expect(drugDealRights).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugDealRights).toContainText("商业化");
  await expect(drugDealRights).toContainText("大中华区");
  await expect(drugDealRights).toContainText("独占");
  await expect(drugDealRights).toContainText("Exclusive commercialization rights for the controlled browser asset");
  await drugDeals.getByRole("button", { name: regulatoryDrugName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await expect(page.getByRole("heading", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await drugDeals.getByRole("button", { name: `打开交易详情：Browser deal ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*deal=${dealProfileId}`));
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await drugDealRights
    .getByRole("button", { name: `Browser pipeline company B ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineCollaboratorId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "临床结果与试验" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "药物概览" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);
  await expect(pipelineTable).toContainText(regulatoryDrugName);

  const regulatoryCompanyName = `Browser regulatory company ${fixtureKeyBase}`;
  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: regulatoryCompanyName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}`));
  await expect(page.getByRole("heading", { name: regulatoryCompanyName, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "公司专业档案", exact: true })).toBeVisible();
  await expect(
    page
      .locator("dt")
      .filter({ hasText: /^最高阶段$/ })
      .locator(".."),
  ).toContainText("II 期临床");
  await expect(page.getByRole("button", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "交易" }).click();
  await expect(page).toHaveURL(/section=deals/);
  const companyDeals = page.getByRole("tabpanel");
  await expect(
    companyDeals.getByRole("button", { name: `打开交易详情：Browser deal ${fixtureKeyBase}` }),
  ).toBeVisible();
  const companyDealAsset = companyDeals.getByRole("button", {
    name: new RegExp(`Browser regulatory drug ${fixtureKeyBase} · II期`),
  });
  await expect(companyDealAsset).toBeVisible();
  await companyDealAsset.click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  const companyDealCollaborator = page.getByRole("button", {
    name: new RegExp(`Browser pipeline company B ${fixtureKeyBase} · 被许可方`),
  });
  await expect(companyDealCollaborator).toBeVisible();
  await companyDealCollaborator.click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineCollaboratorId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.goto(`/workspace/research?view=company&entity=${pipelineOrganizationId}`);
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page).toHaveURL(/section=timeline/);
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await expect(page.getByRole("tabpanel")).toContainText(regulatoryDrugName);
  await page.reload();
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: regulatoryDrugName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}`));
  await page.goto(`${pipelineResultsUrl.pathname}${pipelineResultsUrl.search}`);
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);

  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: `Browser pipeline target ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}`));
  await expect(
    page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  return {
    ...context,
    milestoneRange,
    exactOrganizationRelationshipResponse,
    exactOrganizationRelationship,
    exactOrganizationPayload,
    pipelineResultsUrl,
    pipelineTable,
    pipelineResearchUrl,
    sortedPipelineResponse,
    pipelineSortMenu,
    pipelineSortResponse,
    pipelineSortPayload,
    pipelineColumnMenu,
    pipelineViewport,
    stickyIdentityColumn,
    regulatoryDrugName,
    drugProgramProgress,
    drugProgramRights,
    drugClinicalResults,
    drugClinicalTrials,
    drugDeals,
    drugDealRights,
    regulatoryCompanyName,
    companyDeals,
    companyDealAsset,
    companyDealCollaborator,
  };
}
