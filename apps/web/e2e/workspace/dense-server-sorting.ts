import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyDenseServerSorting(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  test.skip(
    !credentials || !fixtureKey || !epidemiologyDiseaseId,
    "Authenticated browser fixture credentials and epidemiology disease ID are required",
  );
  if (!credentials || !fixtureKey || !epidemiologyDiseaseId) return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto(`/workspace/research?view=trials&q=${encodeURIComponent(fixtureKey)}`);
  const trialTable = page.getByRole("table", { name: "临床试验结果" });
  await expect(trialTable).toContainText(`Browser clinical trial ${fixtureKey}`);
  await expect(page.getByText(/全部结果按最近更新降序/)).toBeVisible();
  const sortedTrialResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["registry_id:asc"])
    );
  });
  await trialTable
    .getByRole("columnheader", { name: /注册号与试验/ })
    .getByRole("button")
    .click();
  const trialSortResponse = await sortedTrialResponse;
  expect(trialSortResponse.ok()).toBe(true);
  expect(await trialSortResponse.json()).toMatchObject({
    sort_by: "registry_id",
    sort_direction: "asc",
    sort: [{ field: "registry_id", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["registry_id:asc"]);
  await expect(page.getByText(/全部结果按注册号与试验升序/)).toBeVisible();
  await page.reload();
  await expect(trialTable.getByRole("columnheader", { name: /注册号与试验/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=patents&q=${encodeURIComponent(fixtureKey)}`);
  const patentTable = page.getByRole("table", { name: "专利族结果" });
  await expect(patentTable).toContainText(`Browser patent family ${fixtureKey}`);
  await expect(page.getByText(/全部结果按最早优先权降序/)).toBeVisible();
  const sortedPatentResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/patent-families" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["family_identifier:asc"])
    );
  });
  await patentTable
    .getByRole("columnheader", { name: /专利族与标题/ })
    .getByRole("button")
    .click();
  const patentSortResponse = await sortedPatentResponse;
  expect(patentSortResponse.ok()).toBe(true);
  expect(await patentSortResponse.json()).toMatchObject({
    sort_by: "family_identifier",
    sort_direction: "asc",
    sort: [{ field: "family_identifier", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["family_identifier:asc"]);
  await expect(page.getByText(/全部结果按专利族与标题升序/)).toBeVisible();
  await page.reload();
  await expect(patentTable.getByRole("columnheader", { name: /专利族与标题/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=news&q=${encodeURIComponent(fixtureKey)}`);
  const newsTable = page.getByRole("table", { name: "新闻与会议结果" });
  await expect(newsTable).toContainText(`Browser news event ${fixtureKey}`);
  await expect(page.getByText(/全部结果按发布日期降序/)).toBeVisible();
  const sortedNewsResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/news-events" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["title:asc"])
    );
  });
  await newsTable
    .getByRole("columnheader", { name: /标题与摘要/ })
    .getByRole("button")
    .click();
  const newsSortResponse = await sortedNewsResponse;
  expect(newsSortResponse.ok()).toBe(true);
  expect(await newsSortResponse.json()).toMatchObject({
    sort_by: "title",
    sort_direction: "asc",
    sort: [{ field: "title", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["title:asc"]);
  await expect(page.getByText(/全部结果按标题与摘要升序/)).toBeVisible();
  await page.reload();
  await expect(newsTable.getByRole("columnheader", { name: /标题与摘要/ })).toHaveAttribute("aria-sort", "ascending");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  const diseaseName = `Browser epidemiology disease ${fixtureKey}`;
  await page.goto(`/workspace/research?view=disease&entity=${epidemiologyDiseaseId}`);
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}`));
  await expect(page.getByRole("heading", { name: diseaseName })).toBeVisible();
  await expect(page.getByText("疾病负担观测", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "最新疾病负担观测" })).toContainText("158,000");

  await page.getByRole("tab", { name: "流行病学" }).click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}&section=epidemiology`));
  await expect(page.getByRole("table", { name: "疾病流行病学观测" })).toContainText(
    "Controlled browser acceptance methodology",
  );
  await page.getByRole("button", { name: "进入完整数据库" }).click();
  await expect(page).toHaveURL(new RegExp(`view=epidemiology&disease_entity_id=${epidemiologyDiseaseId}`));
  await expect(page.getByRole("group", { name: "疾病检索与选择" })).toContainText(diseaseName);
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText("158,000");

  await page.goto(`/workspace/research?view=entity&entity=${epidemiologyDiseaseId}&section=programs`);
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}&section=pipeline`));
  await expect(page.getByRole("heading", { name: diseaseName })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
