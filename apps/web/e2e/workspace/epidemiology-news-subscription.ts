import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyEpidemiologyNewsSubscription(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(90_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  const epidemiologyPatientPopulationId = process.env.E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID;
  const epidemiologyObservationId = process.env.E2E_EPIDEMIOLOGY_OBSERVATION_ID;
  const epidemiologyComparableObservationId = process.env.E2E_EPIDEMIOLOGY_COMPARABLE_OBSERVATION_ID;
  const epidemiologyIncompatibleObservationId = process.env.E2E_EPIDEMIOLOGY_INCOMPATIBLE_OBSERVATION_ID;
  const newsEventId = process.env.E2E_NEWS_EVENT_ID;
  const newsNegativeEventId = process.env.E2E_NEWS_NEGATIVE_EVENT_ID;
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !epidemiologyDiseaseId ||
      !epidemiologyPatientPopulationId ||
      !epidemiologyObservationId ||
      !epidemiologyComparableObservationId ||
      !epidemiologyIncompatibleObservationId ||
      !newsEventId ||
      !newsNegativeEventId,
    "Authenticated browser fixture credentials and epidemiology disease ID are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !epidemiologyDiseaseId ||
    !epidemiologyPatientPopulationId ||
    !epidemiologyObservationId ||
    !epidemiologyComparableObservationId ||
    !epidemiologyIncompatibleObservationId ||
    !newsEventId ||
    !newsNegativeEventId
  )
    return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const epidemiologyQuery = new URLSearchParams({
    view: "epidemiology",
    q: fixtureKeyBase,
    disease_entity_id: epidemiologyDiseaseId,
    measure: "prevalence",
    geography: "China",
    unit: "patients",
    patient_population_id: epidemiologyPatientPopulationId,
    population_scope: "adults",
    age_group: "18+",
    sex: "all",
    period_start_from: "2025-01-01",
    period_end_to: "2025-12-31",
    sort: "value:desc",
  });
  await page.goto(`/workspace/research?${epidemiologyQuery}`);
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText(
    `Browser epidemiology disease ${fixtureKeyBase}`,
  );
  const trendResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === `/api/v1/epidemiology-trends/${epidemiologyDiseaseId}` &&
      url.searchParams.get("anchor_observation_id") === epidemiologyObservationId
    );
  });
  await page
    .getByRole("table", { name: "流行病学结果" })
    .getByRole("button", { name: `查看 Browser epidemiology disease ${fixtureKeyBase} 同口径趋势` })
    .click();
  const trendResponse = await trendResponsePromise;
  const trendPayload = (await trendResponse.json()) as {
    anchor_observation_id: string | null;
    total: number;
    items: Array<{ id: string }>;
  };
  expect(trendPayload.anchor_observation_id).toBe(epidemiologyObservationId);
  expect(trendPayload.total).toBe(2);
  expect(new Set(trendPayload.items.map((item) => item.id))).toEqual(
    new Set([epidemiologyComparableObservationId, epidemiologyObservationId]),
  );
  expect(trendPayload.items.some((item) => item.id === epidemiologyIncompatibleObservationId)).toBe(false);
  await expect(
    page.getByRole("region", { name: `Browser epidemiology disease ${fixtureKeyBase} 同口径趋势` }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭趋势" }).click();
  const epidemiologySubscriptionName = `Browser epidemiology subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const epidemiologySaveForm = page.getByRole("dialog", { name: "保存当前流行病学检索" });
  await epidemiologySaveForm.getByLabel("名称").fill(epidemiologySubscriptionName);
  await epidemiologySaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("流行病学检索已保存并启用监控")).toBeVisible();

  const newsQuery = new URLSearchParams({
    view: "news",
    q: fixtureKeyBase,
    event_type: "conference_abstract",
    publisher: `Browser publisher ${fixtureKeyBase}`,
    language: "en",
    venue: "ASCO 2026",
    published_from: "2026-07-01",
    published_to: "2026-07-31",
    content_scope: "research",
    display: "timeline",
    sort: "title:asc",
  });
  const newsResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/news-events" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("event_type") === "conference_abstract" &&
      url.searchParams.get("publisher") === `Browser publisher ${fixtureKeyBase}` &&
      url.searchParams.get("language") === "en" &&
      url.searchParams.get("venue") === "ASCO 2026" &&
      url.searchParams.get("content_scope") === "research"
    );
  });
  await page.goto(`/workspace/research?${newsQuery}`);
  const newsResponse = await newsResponsePromise;
  const newsPayload = (await newsResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(newsPayload.total).toBe(1);
  expect(newsPayload.items.map((item) => item.id)).toEqual([newsEventId]);
  expect(newsPayload.items.some((item) => item.id === newsNegativeEventId)).toBe(false);
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toContainText(
    `Browser news event ${fixtureKeyBase}`,
  );
  const newsSubscriptionName = `Browser news subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const newsSaveForm = page.getByRole("dialog", { name: "保存当前新闻与会议检索" });
  await newsSaveForm.getByLabel("名称").fill(newsSubscriptionName);
  await newsSaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("新闻与会议检索已保存并启用监控")).toBeVisible();

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const epidemiologyRow = page.getByRole("row").filter({ hasText: epidemiologySubscriptionName });
  await expect(epidemiologyRow).toContainText("流行病学");
  await epidemiologyRow.getByRole("button", { name: `运行 ${epidemiologySubscriptionName}` }).click();
  for (const [name, value] of epidemiologyQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const epidemiologyFilters = page.getByRole("form", { name: "流行病学筛选" });
  await expect(epidemiologyFilters.getByLabel("统计指标")).toHaveValue("prevalence");
  await expect(epidemiologyFilters.getByLabel("地区")).toHaveValue("China");
  await expect(epidemiologyFilters.getByLabel("标准患者人群")).toHaveValue(epidemiologyPatientPopulationId);
  await expect(
    page.getByRole("table", { name: "流行病学结果" }).getByRole("columnheader", { name: /指标 \/ 估计值/ }),
  ).toHaveAttribute("aria-sort", "descending");
  await page.reload();
  await expect(epidemiologyFilters.getByLabel("人群口径")).toHaveValue("adults");
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText(
    `Browser epidemiology disease ${fixtureKeyBase}`,
  );

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const newsRow = page.getByRole("row").filter({ hasText: newsSubscriptionName });
  await expect(newsRow).toContainText("新闻与会议");
  await newsRow.getByRole("button", { name: `运行 ${newsSubscriptionName}` }).click();
  for (const [name, value] of newsQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const newsFilters = page.getByRole("form", { name: "新闻与会议筛选" });
  await expect(newsFilters.getByLabel("事件类型")).toHaveValue("conference_abstract");
  await expect(newsFilters.getByLabel("会议 / 场景")).toHaveValue("ASCO 2026");
  await expect(page.getByRole("button", { name: "研究发布时间线" })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toContainText(
    `Browser news event ${fixtureKeyBase}`,
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
