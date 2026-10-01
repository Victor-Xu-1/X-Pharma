import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyEpidemiologyPatientPopulation({
  page,
}: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  const populationId = "550e8400-e29b-41d4-a716-446655440003";
  const diseaseId = "550e8400-e29b-41d4-a716-446655440001";
  const requestedPopulationIds: Array<string | null> = [];
  await page.route("**/api/v1/**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "epidemiology-user",
          tenant_id: "epidemiology-tenant",
          email: "epidemiology@example.test",
          display_name: "Epidemiology Analyst",
          role: "analyst",
        },
      });
    }
    const observation = {
      id: "550e8400-e29b-41d4-a716-446655440010",
      observation_identifier: "WHO-NSCLC-CN-2025",
      disease_entity_id: diseaseId,
      patient_population_id: populationId,
      measure: "prevalence",
      value: 158000,
      lower_bound: 150000,
      upper_bound: 166000,
      unit: "patients",
      geography: "China",
      population_scope: "adults",
      age_group: "18+",
      sex: "all",
      period_start: "2025-01-01T00:00:00Z",
      period_end: "2025-12-31T00:00:00Z",
      sample_size: 12500,
      methodology: "Registry-calibrated prevalence model",
      publisher_entity_id: null,
      source_document_id: "550e8400-e29b-41d4-a716-446655440011",
      disease_entity: { id: diseaseId, name: "EGFR-positive NSCLC", entity_type: "disease" },
      publisher_entity: null,
      patient_population: {
        id: populationId,
        population_key: "egfr-positive-nsclc-cn",
        name: "中国 EGFR 阳性 NSCLC 患者",
        description: "标准化生物标志物患者人群",
        attributes: { biomarker: "EGFR-positive" },
        disease_entities: [{ id: diseaseId, name: "EGFR-positive NSCLC", entity_type: "disease" }],
        target_entities: [{ id: "550e8400-e29b-41d4-a716-446655440004", name: "EGFR", entity_type: "target" }],
      },
    };
    if (path === "/api/v1/epidemiology-observations") {
      requestedPopulationIds.push(requestUrl.searchParams.get("patient_population_id"));
      return route.fulfill({
        json: {
          items: [observation],
          total: 1,
          limit: 100,
          offset: 0,
          facets: {
            measure: { prevalence: 1 },
            geography: { China: 1 },
            unit: { patients: 1 },
            population_scope: { adults: 1 },
            age_group: { "18+": 1 },
            sex: { all: 1 },
            disease: { "EGFR-positive NSCLC": 1 },
            publisher: {},
          },
          patient_populations: [{ id: populationId, name: "中国 EGFR 阳性 NSCLC 患者", count: 1 }],
          query_schema_version: "pharma.epidemiology.search.v3",
          sort_by: "period_end",
          sort_direction: "desc",
          sort: [{ field: "period_end", direction: "desc" }],
          applied_filters: requestUrl.searchParams.get("patient_population_id")
            ? [{ field: "patient_population_id", operator: "eq", value: populationId }]
            : [],
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    if (path === `/api/v1/epidemiology-trends/${diseaseId}`) {
      requestedPopulationIds.push(requestUrl.searchParams.get("patient_population_id"));
      return route.fulfill({
        json: {
          disease: observation.disease_entity,
          items: [observation],
          total: 1,
          truncated: false,
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=epidemiology");
  await expect(page.getByRole("table", { name: "流行病学结果" })).toBeVisible();
  await expect(page.getByText("中国 EGFR 阳性 NSCLC 患者", { exact: true })).toBeVisible();
  await page.getByLabel("标准患者人群").selectOption(populationId);
  await page.getByRole("button", { name: "查询" }).click();
  await expect(page).toHaveURL(new RegExp(`patient_population_id=${populationId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("标准患者人群");
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText(populationId);
  await page.getByRole("button", { name: "查看 EGFR-positive NSCLC 同口径趋势" }).click();
  await expect(page.getByRole("region", { name: "EGFR-positive NSCLC 同口径趋势" })).toBeVisible();
  expect(requestedPopulationIds).toContain(populationId);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
