import { expect } from "@playwright/test";
import { expandProfessionalQuery, verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyPipelineQuerySignals } from "./pipeline-query-signals";

export async function verifyProfessionalQueryDomains(context: Awaited<ReturnType<typeof verifyPipelineQuerySignals>>) {
  const { page, fixtureKeyBase, epidemiologyDiseaseId, epidemiologyPatientPopulationId, epidemiologyObservationId } =
    context;
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const regulatoryProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await regulatoryProfessionalQuery.getByRole("button", { name: "监管与安全", exact: true }).click();
  await expect(regulatoryProfessionalQuery.getByLabel("监管机构")).toContainText("FDA (2)");
  await regulatoryProfessionalQuery.getByLabel("监管机构").selectOption("FDA");
  await regulatoryProfessionalQuery.getByLabel("辖区").selectOption("US");
  await regulatoryProfessionalQuery.getByLabel("事件类型").selectOption("approval");
  await regulatoryProfessionalQuery.getByLabel("事件状态").selectOption("approved");
  await regulatoryProfessionalQuery.getByLabel("监管决定日期时间范围").selectOption("custom");
  const professionalDecisionRange = regulatoryProfessionalQuery.getByRole("group", { name: "监管决定日期" });
  await professionalDecisionRange.getByLabel("起").fill("2026-02-20");
  await professionalDecisionRange.getByLabel("止").fill("2026-02-20");
  await regulatoryProfessionalQuery.getByText("更多监管与安全条件").click();
  await regulatoryProfessionalQuery.getByLabel("认定资格").selectOption("breakthrough_therapy");
  await regulatoryProfessionalQuery.getByLabel("标签变更").selectOption("initial_label");
  await regulatoryProfessionalQuery.getByLabel("黑框警告").selectOption("true");
  await regulatoryProfessionalQuery.getByLabel("安全信号").selectOption("adverse_event");
  await regulatoryProfessionalQuery.getByLabel("严重程度").selectOption("serious");
  await regulatoryProfessionalQuery.getByLabel("信号状态").selectOption("confirmed");
  await regulatoryProfessionalQuery.getByLabel("来源更新日期时间范围").selectOption("custom");
  const professionalSourceRange = regulatoryProfessionalQuery.getByRole("group", { name: "来源更新日期" });
  await professionalSourceRange.getByLabel("起").fill("2026-02-22");
  await professionalSourceRange.getByLabel("止").fill("2026-02-22");
  const professionalRegulatoryResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("agency") === "FDA" &&
      url.searchParams.get("jurisdiction") === "US" &&
      url.searchParams.get("event_type") === "approval" &&
      url.searchParams.get("status") === "approved" &&
      url.searchParams.get("designation_type") === "breakthrough_therapy" &&
      url.searchParams.get("label_change_type") === "initial_label" &&
      url.searchParams.get("has_boxed_warning") === "true" &&
      url.searchParams.get("safety_signal_type") === "adverse_event" &&
      url.searchParams.get("safety_severity") === "serious" &&
      url.searchParams.get("safety_status") === "confirmed" &&
      url.searchParams.get("decision_from") === "2026-02-20T00:00:00.000Z" &&
      url.searchParams.get("decision_to") === "2026-02-20T23:59:59.999Z" &&
      url.searchParams.get("source_updated_from") === "2026-02-22T00:00:00.000Z" &&
      url.searchParams.get("source_updated_to") === "2026-02-22T23:59:59.999Z"
    );
  });
  await regulatoryProfessionalQuery.getByRole("button", { name: "查询 监管与安全" }).click();
  expect((await professionalRegulatoryResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=regulatory/);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-02-20/);
  await expect(page).toHaveURL(/source_updated_from=2026-02-22/);
  const professionalRegulatoryTable = page.getByRole("table", { name: "监管事件结果" });
  await expect(professionalRegulatoryTable).toContainText(`Browser regulatory event ${fixtureKeyBase}`);
  await expect(professionalRegulatoryTable).not.toContainText(`Browser regulatory negative event ${fixtureKeyBase}`);
  await page.reload();
  const restoredProfessionalRegulatoryFilters = page.getByRole("form", { name: "监管事件筛选" });
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("监管机构")).toHaveValue("FDA");
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("信号状态")).toHaveValue("confirmed");
  await expect(restoredProfessionalRegulatoryFilters.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  const restoredProfessionalDecisionRange = restoredProfessionalRegulatoryFilters.getByRole("group", {
    name: "决定日期",
  });
  await expect(restoredProfessionalDecisionRange.getByLabel("起")).toHaveValue("2026-02-20");
  await expect(restoredProfessionalDecisionRange.getByLabel("止")).toHaveValue("2026-02-20");
  await expect(professionalRegulatoryTable).toContainText(`Browser regulatory event ${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/regulatory-event-timeline",
    resultSurface: professionalRegulatoryTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const epidemiologyProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await epidemiologyProfessionalQuery.getByRole("button", { name: "流行病学", exact: true }).click();
  const professionalEpidemiologyDiseaseName = `Browser epidemiology disease ${fixtureKeyBase}`;
  await epidemiologyProfessionalQuery.getByLabel("疾病筛选").fill(professionalEpidemiologyDiseaseName);
  await epidemiologyProfessionalQuery
    .getByRole("option", { name: new RegExp(professionalEpidemiologyDiseaseName) })
    .click();
  await expect(epidemiologyProfessionalQuery.getByLabel("统计指标")).toContainText("患病率");
  await epidemiologyProfessionalQuery.getByLabel("统计指标").selectOption("prevalence");
  await epidemiologyProfessionalQuery.getByLabel("地区").selectOption("China");
  await epidemiologyProfessionalQuery.getByLabel("单位").selectOption("patients");
  await epidemiologyProfessionalQuery.getByLabel("标准患者人群").selectOption(epidemiologyPatientPopulationId);
  await epidemiologyProfessionalQuery.getByLabel("人群口径").selectOption("adults");
  await epidemiologyProfessionalQuery.getByLabel("年龄组").selectOption("18+");
  await epidemiologyProfessionalQuery.getByLabel("性别").selectOption("all");
  await epidemiologyProfessionalQuery.getByLabel("统计周期时间范围").selectOption("custom");
  const professionalEpidemiologyPeriod = epidemiologyProfessionalQuery.getByRole("group", { name: "统计周期" });
  await professionalEpidemiologyPeriod.getByLabel("起").fill("2025-01-01");
  await professionalEpidemiologyPeriod.getByLabel("止").fill("2025-12-31");
  const professionalEpidemiologyResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/epidemiology-observations" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("disease_entity_id") === epidemiologyDiseaseId &&
      url.searchParams.get("measure") === "prevalence" &&
      url.searchParams.get("geography") === "China" &&
      url.searchParams.get("unit") === "patients" &&
      url.searchParams.get("patient_population_id") === epidemiologyPatientPopulationId &&
      url.searchParams.get("population_scope") === "adults" &&
      url.searchParams.get("age_group") === "18+" &&
      url.searchParams.get("sex") === "all" &&
      url.searchParams.get("period_start_from") === "2025-01-01T00:00:00Z" &&
      url.searchParams.get("period_end_to") === "2025-12-31T23:59:59Z"
    );
  });
  await epidemiologyProfessionalQuery.getByRole("button", { name: "查询 流行病学" }).click();
  const professionalEpidemiologyPayload = (await professionalEpidemiologyResponse).json() as Promise<{
    total: number;
    items: Array<{ id: string }>;
  }>;
  await expect(professionalEpidemiologyPayload).resolves.toMatchObject({
    total: 1,
    items: [{ id: epidemiologyObservationId }],
  });
  await expect(page).toHaveURL(/view=epidemiology/);
  await expect(page).toHaveURL(new RegExp(`disease_entity_id=${epidemiologyDiseaseId}`));
  await expect(page).toHaveURL(new RegExp(`patient_population_id=${epidemiologyPatientPopulationId}`));
  await expect(page).toHaveURL(/population_scope=adults/);
  await expect(page).toHaveURL(/age_group=18%2B/);
  await expect(page).toHaveURL(/period_start_from=2025-01-01/);
  const professionalEpidemiologyTable = page.getByRole("table", { name: "流行病学结果" });
  await expect(professionalEpidemiologyTable).toContainText(professionalEpidemiologyDiseaseName);
  await page.reload();
  const restoredProfessionalEpidemiologyFilters = page.getByRole("form", { name: "流行病学筛选" });
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("统计指标")).toHaveValue("prevalence");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("地区")).toHaveValue("China");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("单位")).toHaveValue("patients");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("标准患者人群")).toHaveValue(
    epidemiologyPatientPopulationId,
  );
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("人群口径")).toHaveValue("adults");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("年龄组")).toHaveValue("18+");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("性别")).toHaveValue("all");
  await expect(professionalEpidemiologyTable).toContainText(professionalEpidemiologyDiseaseName);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/epidemiology-observations",
    resultSurface: professionalEpidemiologyTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return {
    ...context,
    regulatoryProfessionalQuery,
    professionalDecisionRange,
    professionalSourceRange,
    professionalRegulatoryResponse,
    professionalRegulatoryTable,
    restoredProfessionalRegulatoryFilters,
    restoredProfessionalDecisionRange,
    epidemiologyProfessionalQuery,
    professionalEpidemiologyDiseaseName,
    professionalEpidemiologyPeriod,
    professionalEpidemiologyResponse,
    professionalEpidemiologyPayload,
    professionalEpidemiologyTable,
    restoredProfessionalEpidemiologyFilters,
  };
}
