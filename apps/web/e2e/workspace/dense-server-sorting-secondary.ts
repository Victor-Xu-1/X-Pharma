import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";

export async function verifyDenseServerSortingSecondary(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKey, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKey) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto(`/workspace/research?view=deals&q=${encodeURIComponent(fixtureKey)}`);
  const dealTable = page.getByRole("table", { name: "交易结果" });
  await expect(dealTable).toContainText(`Browser deal ${fixtureKey}`);
  await expect(page.getByText(/全部结果按初始披露降序/)).toBeVisible();
  const sortedDealResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/deal-transactions" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["name:asc"])
    );
  });
  await dealTable
    .getByRole("columnheader", { name: /交易名称/ })
    .getByRole("button")
    .click();
  const dealSortResponse = await sortedDealResponse;
  expect(dealSortResponse.ok()).toBe(true);
  expect(await dealSortResponse.json()).toMatchObject({
    sort_by: "name",
    sort_direction: "asc",
    sort: [{ field: "name", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
  await page.reload();
  await expect(dealTable.getByRole("columnheader", { name: /交易名称/ })).toHaveAttribute("aria-sort", "ascending");

  await page.goto(`/workspace/research?view=regulatory&q=${encodeURIComponent(fixtureKey)}`);
  const regulatoryTable = page.getByRole("table", { name: "监管事件结果" });
  await expect(regulatoryTable).toContainText(`Browser regulatory event ${fixtureKey}`);
  await expect(page.getByText(/全部结果按决定日期降序/)).toBeVisible();
  const sortedRegulatoryResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["title:asc"])
    );
  });
  await regulatoryTable
    .getByRole("columnheader", { name: /监管事件/ })
    .getByRole("button")
    .click();
  const regulatorySortResponse = await sortedRegulatoryResponse;
  expect(regulatorySortResponse.ok()).toBe(true);
  expect(await regulatorySortResponse.json()).toMatchObject({
    sort_by: "title",
    sort_direction: "asc",
    sort: [{ field: "title", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["title:asc"]);
  await page.reload();
  await expect(regulatoryTable.getByRole("columnheader", { name: /监管事件/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=epidemiology&q=${encodeURIComponent(fixtureKey)}`);
  const epidemiologyTable = page.getByRole("table", { name: "流行病学结果" });
  await expect(epidemiologyTable).toContainText(`Browser epidemiology disease ${fixtureKey}`);
  await expect(page.getByText(/全部结果按观察期降序/)).toBeVisible();
  const sortedEpidemiologyResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/epidemiology-observations" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["value:desc"])
    );
  });
  await epidemiologyTable
    .getByRole("columnheader", { name: /指标 \/ 估计值/ })
    .getByRole("button")
    .click();
  const epidemiologySortResponse = await sortedEpidemiologyResponse;
  expect(epidemiologySortResponse.ok()).toBe(true);
  expect(await epidemiologySortResponse.json()).toMatchObject({
    sort_by: "value",
    sort_direction: "desc",
    sort: [{ field: "value", direction: "desc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["value:desc"]);
  await page.reload();
  await expect(epidemiologyTable.getByRole("columnheader", { name: /指标 \/ 估计值/ })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
