import { expect } from "@playwright/test";
import { expandProfessionalQuery, verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyClinicalQueryAndResults } from "./clinical-query-and-results";

export async function verifyPipelineQuerySignals(context: Awaited<ReturnType<typeof verifyClinicalQueryAndResults>>) {
  const {
    page,
    fixtureKeyBase,
    pipelineTargetId,
    pipelineOrganizationId,
    regulatorySubjectId,
    regulatoryIndicationId,
  } = context;
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const patentProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await patentProfessionalQuery.getByRole("button", { name: "专利情报", exact: true }).click();
  await expect(patentProfessionalQuery.getByLabel("法律状态")).toContainText("有效");
  await expect(patentProfessionalQuery.getByLabel("关联实体类型")).toHaveValue("target");
  const patentLinkedEntityName = `Browser pipeline target ${fixtureKeyBase}`;
  await patentProfessionalQuery.getByLabel("关联实体筛选").fill(patentLinkedEntityName);
  await patentProfessionalQuery.getByRole("option", { name: new RegExp(patentLinkedEntityName) }).click();
  await patentProfessionalQuery.getByLabel("申请人").fill(`Browser applicant ${fixtureKeyBase}`);
  await patentProfessionalQuery.getByLabel("法律状态").selectOption("ACTIVE");
  await patentProfessionalQuery.getByLabel("优先权日期时间范围").selectOption("custom");
  const professionalPriorityRange = patentProfessionalQuery.getByRole("group", { name: "优先权日期" });
  await professionalPriorityRange.getByLabel("起").fill("2024-01-10");
  await professionalPriorityRange.getByLabel("止").fill("2024-01-10");
  await patentProfessionalQuery.getByLabel("到期日期时间范围").selectOption("custom");
  const professionalExpirationRange = patentProfessionalQuery.getByRole("group", { name: "到期日期" });
  await professionalExpirationRange.getByLabel("起").fill("2044-01-10");
  await professionalExpirationRange.getByLabel("止").fill("2044-01-10");
  const professionalPatentResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/patent-families" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("entity_id") === pipelineTargetId &&
      url.searchParams.get("applicant") === `Browser applicant ${fixtureKeyBase}` &&
      url.searchParams.get("legal_status") === "ACTIVE" &&
      url.searchParams.get("priority_from") === "2024-01-10T00:00:00.000Z" &&
      url.searchParams.get("priority_to") === "2024-01-10T23:59:59.999Z" &&
      url.searchParams.get("expiration_from") === "2044-01-10T00:00:00.000Z" &&
      url.searchParams.get("expiration_to") === "2044-01-10T23:59:59.999Z"
    );
  });
  await patentProfessionalQuery.getByRole("button", { name: "查询 专利情报" }).click();
  expect((await professionalPatentResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=patents/);
  await expect(page).toHaveURL(new RegExp(`entity_id=${pipelineTargetId}`));
  await expect(page).toHaveURL(/applicant=Browser\+applicant/);
  await expect(page).toHaveURL(/legal_status=ACTIVE/);
  await expect(page).toHaveURL(/priority_from=2024-01-10/);
  await expect(page).toHaveURL(/expiration_to=2044-01-10/);
  const professionalPatentTable = page.getByRole("table", { name: "专利族结果" });
  await expect(professionalPatentTable).toContainText(`WO-E2E-${fixtureKeyBase}`);
  await page.reload();
  const restoredPatentFilters = page.getByRole("form", { name: "专利族筛选" });
  await expect(restoredPatentFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredPatentFilters.getByLabel("申请人")).toHaveValue(`Browser applicant ${fixtureKeyBase}`);
  await expect(restoredPatentFilters.getByLabel("法律状态")).toHaveValue("ACTIVE");
  const restoredPriorityRange = restoredPatentFilters.getByRole("group", { name: "优先权日期" });
  await expect(restoredPriorityRange.getByLabel("起")).toHaveValue("2024-01-10");
  await expect(restoredPriorityRange.getByLabel("止")).toHaveValue("2024-01-10");
  const restoredExpirationRange = restoredPatentFilters.getByRole("group", { name: "预计到期日期" });
  await expect(restoredExpirationRange.getByLabel("起")).toHaveValue("2044-01-10");
  await expect(restoredExpirationRange.getByLabel("止")).toHaveValue("2044-01-10");
  await expect(professionalPatentTable).toContainText(`WO-E2E-${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/patent-families",
    resultSurface: professionalPatentTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const dealProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await dealProfessionalQuery.getByRole("button", { name: "交易与公司", exact: true }).click();
  await expect(dealProfessionalQuery.getByLabel("交易类型")).toContainText("许可");
  const professionalDealAssetName = `Browser regulatory drug ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("交易药品筛选").fill(professionalDealAssetName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealAssetName) }).click();
  const professionalDealTargetName = `Browser pipeline target ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("关联靶点筛选").fill(professionalDealTargetName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealTargetName) }).click();
  const professionalDealDiseaseName = `Browser regulatory indication ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("关联适应症筛选").fill(professionalDealDiseaseName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealDiseaseName) }).click();
  const professionalDealPartyName = `Browser regulatory company ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("参与机构筛选").fill(professionalDealPartyName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealPartyName) }).click();
  await dealProfessionalQuery.getByLabel("交易类型").selectOption("license");
  await dealProfessionalQuery.getByLabel("交易状态").selectOption("active");
  await dealProfessionalQuery.getByLabel("交易方向").selectOption("outbound");
  await dealProfessionalQuery.getByLabel("交易披露日期时间范围").selectOption("custom");
  const professionalDealAnnouncedRange = dealProfessionalQuery.getByRole("group", { name: "交易披露日期" });
  await professionalDealAnnouncedRange.getByLabel("起").fill("2026-01-20");
  await professionalDealAnnouncedRange.getByLabel("止").fill("2026-01-20");
  await dealProfessionalQuery.getByText("更多交易条件").click();
  await dealProfessionalQuery.getByLabel("方向参照地区").fill("US");
  await dealProfessionalQuery.getByLabel("交易地域").selectOption("global");
  const professionalDealModalities = dealProfessionalQuery.getByRole("group", { name: "资产模态" });
  await professionalDealModalities.getByLabel("资产模态：全部").click();
  await professionalDealModalities.getByRole("checkbox", { name: /small molecule/ }).click();
  const professionalDealProgramTags = dealProfessionalQuery.getByRole("group", { name: "资产项目标签" });
  await professionalDealProgramTags.getByLabel("资产项目标签：全部").click();
  await professionalDealProgramTags.getByRole("checkbox", { name: /first_in_class/ }).click();
  await dealProfessionalQuery.getByLabel("参与角色").selectOption("licensor");
  await dealProfessionalQuery.getByLabel("机构所在地区").selectOption("US");
  await dealProfessionalQuery.getByLabel("机构类型").selectOption("biopharma");
  await dealProfessionalQuery.getByLabel("交易时阶段").selectOption("phase_1");
  await dealProfessionalQuery.getByLabel("当前最高阶段").selectOption("phase_2");
  await dealProfessionalQuery.getByLabel("权益类型").selectOption("commercialization");
  await dealProfessionalQuery.getByLabel("权益地区").selectOption("Greater China");
  await dealProfessionalQuery.getByLabel("币种").selectOption("USD");
  await dealProfessionalQuery.getByLabel("信息更新日期时间范围").selectOption("custom");
  const professionalDealUpdatedRange = dealProfessionalQuery.getByRole("group", { name: "信息更新日期" });
  await professionalDealUpdatedRange.getByLabel("起").fill("2026-03-15");
  await professionalDealUpdatedRange.getByLabel("止").fill("2026-03-15");
  await dealProfessionalQuery.getByLabel("首付款下限").fill("10000000");
  await dealProfessionalQuery.getByLabel("首付款上限").fill("30000000");
  await dealProfessionalQuery.getByLabel("潜在总额下限").fill("100000000");
  await dealProfessionalQuery.getByLabel("潜在总额上限").fill("500000000");
  const professionalDealResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/deal-transactions" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("deal_type") === "license" &&
      url.searchParams.get("status") === "active" &&
      url.searchParams.get("direction") === "outbound" &&
      url.searchParams.get("direction_reference_jurisdiction") === "US" &&
      url.searchParams.get("territory") === "global" &&
      url.searchParams.get("asset_entity_id") === regulatorySubjectId &&
      url.searchParams.get("target_entity_id") === pipelineTargetId &&
      url.searchParams.get("disease_entity_id") === regulatoryIndicationId &&
      url.searchParams.get("party_entity_id") === pipelineOrganizationId &&
      url.searchParams.get("party_role") === "licensor" &&
      url.searchParams.get("party_country_region") === "US" &&
      url.searchParams.get("party_organization_type") === "biopharma" &&
      url.searchParams.get("development_phase_at_transaction") === "phase_1" &&
      url.searchParams.get("current_development_phase") === "phase_2" &&
      url.searchParams.get("right_type") === "commercialization" &&
      url.searchParams.get("rights_territory") === "Greater China" &&
      url.searchParams.get("currency") === "USD" &&
      url.searchParams.get("announced_from") === "2026-01-20T00:00:00.000Z" &&
      url.searchParams.get("announced_to") === "2026-01-20T23:59:59.999Z" &&
      url.searchParams.get("source_updated_from") === "2026-03-15T00:00:00.000Z" &&
      url.searchParams.get("source_updated_to") === "2026-03-15T23:59:59.999Z" &&
      url.searchParams.get("upfront_amount_min") === "10000000" &&
      url.searchParams.get("upfront_amount_max") === "30000000" &&
      url.searchParams.get("total_potential_amount_min") === "100000000" &&
      url.searchParams.get("total_potential_amount_max") === "500000000" &&
      url.searchParams.getAll("asset_modality").includes("small molecule") &&
      url.searchParams.getAll("asset_program_tag").includes("first_in_class")
    );
  });
  await dealProfessionalQuery.getByRole("button", { name: "查询 交易与公司" }).click();
  expect((await professionalDealResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=deals/);
  await expect(page).toHaveURL(new RegExp(`asset_entity_id=${regulatorySubjectId}`));
  await expect(page).toHaveURL(new RegExp(`target_entity_id=${pipelineTargetId}`));
  await expect(page).toHaveURL(new RegExp(`disease_entity_id=${regulatoryIndicationId}`));
  await expect(page).toHaveURL(new RegExp(`party_entity_id=${pipelineOrganizationId}`));
  await expect(page).toHaveURL(/asset_modality=small\+molecule/);
  await expect(page).toHaveURL(/asset_program_tag=first_in_class/);
  const professionalDealTable = page.getByRole("table", { name: "交易结果" });
  await expect(professionalDealTable).toContainText(`Browser deal ${fixtureKeyBase}`);
  await page.reload();
  const restoredProfessionalDealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(restoredProfessionalDealFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredProfessionalDealFilters.getByLabel("交易类型")).toHaveValue("license");
  await expect(restoredProfessionalDealFilters.getByLabel("交易状态")).toHaveValue("active");
  await expect(restoredProfessionalDealFilters.getByLabel("交易方向")).toHaveValue("outbound");
  await expect(professionalDealTable).toContainText(`Browser deal ${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/deal-transactions",
    resultSurface: professionalDealTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return {
    ...context,
    patentProfessionalQuery,
    patentLinkedEntityName,
    professionalPriorityRange,
    professionalExpirationRange,
    professionalPatentResponse,
    professionalPatentTable,
    restoredPatentFilters,
    restoredPriorityRange,
    restoredExpirationRange,
    dealProfessionalQuery,
    professionalDealAssetName,
    professionalDealTargetName,
    professionalDealDiseaseName,
    professionalDealPartyName,
    professionalDealAnnouncedRange,
    professionalDealModalities,
    professionalDealProgramTags,
    professionalDealUpdatedRange,
    professionalDealResponse,
    professionalDealTable,
    restoredProfessionalDealFilters,
  };
}
