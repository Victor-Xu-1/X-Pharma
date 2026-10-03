import { expect, type Route } from "@playwright/test";
import { verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyLoginAndAppearance } from "./login-and-appearance";

export async function verifyQueryCancellationAndPagination(
  context: Awaited<ReturnType<typeof verifyLoginAndAppearance>>,
) {
  const { page, fixtureKeyBase } = context;
  const paginationQuery = `Browser pagination ${fixtureKeyBase}`;
  let releaseDelayedSearch: (() => void) | undefined;
  let markBackendResponseReady: (() => void) | undefined;
  let markDelayedHandlerSettled: (() => void) | undefined;
  const delayedSearch = new Promise<void>((resolve) => {
    releaseDelayedSearch = resolve;
  });
  const backendResponseReady = new Promise<void>((resolve) => {
    markBackendResponseReady = resolve;
  });
  const delayedHandlerSettled = new Promise<void>((resolve) => {
    markDelayedHandlerSettled = resolve;
  });
  let delayedSearchStatus = 0;
  const delayedSearchRoute = async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("q") !== paginationQuery || delayedSearchStatus !== 0) return route.continue();
    const response = await route.fetch();
    delayedSearchStatus = response.status();
    markBackendResponseReady?.();
    await delayedSearch;
    try {
      await route.fulfill({ response });
    } catch (caught) {
      const failure = route.request().failure();
      if (!failure || !/abort|cancel/i.test(failure.errorText)) throw caught;
    } finally {
      markDelayedHandlerSettled?.();
    }
  };
  await page.route("**/api/v1/entities?**", delayedSearchRoute);
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  await backendResponseReady;
  expect(delayedSearchStatus).toBe(200);
  await expect(page.getByText("正在检索结构化情报", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "取消查询" }).click();
  await expect(page.getByText("查询已取消", { exact: true })).toBeVisible();
  releaseDelayedSearch?.();
  await delayedHandlerSettled;
  await page.unroute("**/api/v1/entities?**", delayedSearchRoute);
  await page.getByRole("button", { name: "重新查询" }).click();
  await expect(page.getByRole("navigation", { name: "实体检索结果分页" }).getByText("共 205 条")).toBeVisible();
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/entities",
    resultSurface: page.getByRole("table", { name: "实体检索结果" }),
  });

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  const entityPagination = page.getByRole("navigation", { name: "实体检索结果分页" });
  await expect(entityPagination.getByText("第 1 / 3 页")).toBeVisible();
  await expect(entityPagination.getByText("共 205 条")).toBeVisible();
  const paginationJump = entityPagination.getByRole("form", { name: "跳转页码" });
  await paginationJump.getByLabel("目标页码").fill("4");
  await paginationJump.getByRole("button", { name: "跳转" }).click();
  await expect(entityPagination.getByRole("alert")).toContainText("请输入 1 到 3 之间的页码");
  await expect(page).not.toHaveURL(/offset=/);

  const thirdPageResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/entities" && url.searchParams.get("offset") === "200";
  });
  await paginationJump.getByLabel("目标页码").fill("3");
  await paginationJump.getByRole("button", { name: "跳转" }).click();
  const thirdPageResponse = await thirdPageResponsePromise;
  expect(thirdPageResponse.ok()).toBe(true);
  const thirdPagePayload = (await thirdPageResponse.json()) as {
    items: Array<{ name: string }>;
    offset: number;
    total: number;
  };
  expect(thirdPagePayload).toMatchObject({ offset: 200, total: 205 });
  expect(thirdPagePayload.items).toHaveLength(5);
  await expect(page).toHaveURL(/offset=200/);
  await expect(entityPagination.getByText("第 3 / 3 页")).toBeVisible();
  await expect(entityPagination.getByRole("button", { name: "第 3 页" })).toHaveAttribute("aria-current", "page");
  await page.reload();
  await expect(entityPagination.getByLabel("目标页码")).toHaveValue("3");
  await expect(entityPagination.getByRole("button", { name: "末页" })).toBeDisabled();

  const normalizedPageResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/entities" && url.searchParams.get("offset") === "200";
  });
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}&offset=999`);
  const normalizedPageResponse = await normalizedPageResponsePromise;
  expect(normalizedPageResponse.ok()).toBe(true);
  await expect(page).toHaveURL(/offset=200/);

  await expect(entityPagination.getByText("第 3 / 3 页")).toBeVisible();
  await expect(entityPagination.getByLabel("目标页码")).toHaveValue("3");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return {
    ...context,
    paginationQuery,
    releaseDelayedSearch,
    markBackendResponseReady,
    markDelayedHandlerSettled,
    delayedSearch,
    backendResponseReady,
    delayedHandlerSettled,
    delayedSearchStatus,
    delayedSearchRoute,
    entityPagination,
    paginationJump,
    thirdPageResponsePromise,
    thirdPageResponse,
    thirdPagePayload,
    normalizedPageResponsePromise,
    normalizedPageResponse,
  };
}
