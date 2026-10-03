import { expect } from "@playwright/test";
import { openNavigation } from "../helpers";
import { verifyDenseResultsVisual } from "./dense-results-visual";
import type { verifyQueryCancellationAndPagination } from "./query-cancellation-and-pagination";

export async function verifyDenseResultAndLandscape(
  context: Awaited<ReturnType<typeof verifyQueryCancellationAndPagination>>,
) {
  const { page, fixtureKey, searchTargetId, searchCompanyId, fixtureName, paginationQuery } = context;
  const { denseTable, denseQuality, denseTableShell } = await verifyDenseResultsVisual(context);

  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_csrf");
  if (!csrfCookie?.value) throw new Error("Authenticated session did not issue the CSRF cookie");
  const denseQuery = new URLSearchParams({
    q: paginationQuery,
    sort: "name:asc",
    limit: "100",
  });
  const firstDensePageResponse = await page.request.get(`/api/v1/entities?${denseQuery}`);
  expect(firstDensePageResponse.ok()).toBe(true);
  const firstDensePage = (await firstDensePageResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  denseQuery.set("offset", "200");
  const lastDensePageResponse = await page.request.get(`/api/v1/entities?${denseQuery}`);
  expect(lastDensePageResponse.ok()).toBe(true);
  const lastDensePage = (await lastDensePageResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  const firstDenseEntity = firstDensePage.items[0];
  const lastDenseEntity = lastDensePage.items[0];
  if (!firstDenseEntity || !lastDenseEntity) throw new Error("Dense pagination fixtures are incomplete");

  const crossPageComparisonName = `Browser cross-page list ${fixtureKey}`;
  const createCrossPageComparison = await page.request.post("/api/v1/comparison-sets", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: { name: crossPageComparisonName, visibility: "private" },
  });
  expect(createCrossPageComparison.status()).toBe(201);
  const crossPageComparison = (await createCrossPageComparison.json()) as { id: string };
  await page.getByRole("checkbox", { name: `选择对比 ${firstDenseEntity.name}` }).click();
  const densePagination = page.getByRole("navigation", { name: "实体检索结果分页" });
  await densePagination.getByRole("button", { name: "末页" }).click();
  await expect(page).toHaveURL(/offset=200/);
  await expect(page.getByText("已选 1/20 项", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: `选择对比 ${lastDenseEntity.name}` }).click();
  await expect(page.getByText("已选 2/20 项", { exact: true })).toBeVisible();
  const crossPageAddTrigger = page.getByRole("button", { name: "加入列表" });
  await crossPageAddTrigger.click();
  const crossPagePicker = page.getByRole("dialog", { name: "加入对比列表" });
  const crossPageSetSelect = crossPagePicker.getByLabel("目标列表");
  const crossPagePickerClose = crossPagePicker.getByRole("button", { name: "关闭" });
  const crossPagePickerSubmit = crossPagePicker.getByRole("button", { name: "确认加入" });
  await expect(crossPagePickerClose).toBeFocused();
  await expect(crossPageSetSelect).toBeVisible();
  await expect(crossPagePickerSubmit).toBeEnabled();
  await crossPagePickerClose.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(crossPagePickerSubmit).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(crossPagePickerClose).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(crossPagePicker).toHaveCount(0);
  await expect(crossPageAddTrigger).toBeFocused();
  await crossPageAddTrigger.click();
  await expect(crossPageSetSelect).toBeVisible();
  await crossPageSetSelect.selectOption(crossPageComparison.id);
  const crossPageBatchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/comparison-sets/${crossPageComparison.id}/members/batch`) &&
      response.request().method() === "POST",
  );
  await crossPagePicker.getByRole("button", { name: "确认加入" }).click();
  const crossPageBatch = await crossPageBatchResponse;
  expect(crossPageBatch.status()).toBe(200);
  expect(crossPageBatch.request().postDataJSON()).toEqual({
    entity_ids: [firstDenseEntity.id, lastDenseEntity.id],
    expected_version: 1,
  });
  await expect(page.getByText(`2 个实体已加入 ${crossPageComparisonName}`, { exact: true })).toBeVisible();

  const createEntity = await page.request.post("/api/v1/entities", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: {
      entity_type: "target",
      name: `${fixtureName} draft`,
      description: "Isolated browser acceptance search projection",
      aliases: [`Acceptance ${fixtureKey}`],
      external_ids: { acceptance: `${fixtureKey}-draft` },
      attributes: { organism: "Homo sapiens", acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
    },
  });
  expect(createEntity.status()).toBe(201);
  const draftEntity = (await createEntity.json()) as { id: string; review_status: string };
  expect(draftEntity.review_status).toBe("draft");
  const createdEntity = { id: searchTargetId };
  const companyName = `Browser acceptance company ${fixtureKey}`;
  const createCompany = await page.request.post("/api/v1/entities", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: {
      entity_type: "organization",
      name: `${companyName} draft`,
      description: "Isolated browser acceptance company dossier",
      external_ids: { acceptance: `${fixtureKey}-company-draft` },
      attributes: { acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
    },
  });
  expect(createCompany.status()).toBe(201);
  const draftCompany = (await createCompany.json()) as { id: string; review_status: string };
  expect(draftCompany.review_status).toBe("draft");
  const createdCompany = { id: searchCompanyId };

  await expect
    .poll(async () => {
      const response = await page.request.get(
        `/api/v1/entities?q=${encodeURIComponent(fixtureKey)}&review_status=verified&limit=25`,
      );
      if (!response.ok()) return null;
      const body = (await response.json()) as { engine: string; total: number };
      return { engine: body.engine, total: body.total };
    })
    .toEqual({ engine: "opensearch", total: 2 });

  await openNavigation(page);
  await page.getByRole("button", { name: "情报检索" }).click();
  await page.getByLabel("情报检索词").fill(fixtureKey);
  await page.getByRole("button", { name: "检索", exact: true }).click();
  await expect(page.locator("tbody").getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "情报对象类型" })).toBeVisible();
  await expect(page.getByRole("button", { name: "对象类型：靶点，1 条" })).toBeVisible();
  await page.getByRole("button", { name: /对象类型：靶点/ }).click();
  await expect(page).toHaveURL(/type=target/);
  await page.getByRole("button", { name: /对象类型：研发机构/ }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("types")).toBe("target,organization");
  await expect(page.locator("tbody").getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(page.locator("tbody").getByText(companyName, { exact: true })).toBeVisible();
  await expect(page.getByText(`外部标识精确匹配：acceptance · ${fixtureKey}`, { exact: true })).toBeVisible();
  await expect(page.getByText(`名称相关匹配：${companyName}`, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "统计", exact: true }).click();
  await expect(page).toHaveURL(/display=landscape/);
  const entityLandscape = page.getByRole("region", { name: "实体检索统计分析" });
  await expect(entityLandscape).toContainText("完整命中集");
  await entityLandscape.getByRole("button", { name: "列表", exact: true }).click();
  const entityTypeStats = entityLandscape.getByRole("table", { name: "实体类型统计表" });
  await expect(entityTypeStats).toContainText("靶点");
  await expect(entityTypeStats).toContainText("机构");
  const savedLandscapeName = `Browser entity statistics ${fixtureKey}`;
  await page.getByRole("button", { name: "保存检索" }).click();
  const savedLandscapeDialog = page.getByRole("dialog", { name: "保存当前检索" });
  await savedLandscapeDialog.getByLabel("名称").fill(savedLandscapeName);
  await savedLandscapeDialog.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("基础查询检索已保存并启用监控", { exact: true })).toBeVisible();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page).toHaveURL(/monitor_tab=searches/);
  await page.reload();
  await expect(page.getByRole("tab", { name: "已保存检索" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).toHaveURL(/view=monitoring/);
  await expect(page.getByRole("tab", { name: "提醒中心" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedLandscapeRow = page.getByRole("row").filter({ hasText: savedLandscapeName });
  await expect(savedLandscapeRow).toBeVisible();
  await expect(savedLandscapeRow).toContainText("基础查询 · 靶点、机构");
  await expect(savedLandscapeRow).toContainText("统计表");
  await savedLandscapeRow.getByRole("button", { name: `运行 ${savedLandscapeName}` }).click();
  await expect(page).toHaveURL(/display=landscape/);
  await expect(page).toHaveURL(/analysis_view=table/);
  const replayedEntityLandscape = page.getByRole("region", { name: "实体检索统计分析" });
  await expect(replayedEntityLandscape).toBeVisible();
  await replayedEntityLandscape
    .getByRole("table", { name: "实体类型统计表" })
    .locator("tbody tr")
    .filter({ hasText: "靶点" })
    .getByRole("button", { name: "筛选" })
    .click();
  await expect(page).toHaveURL(/type=target/);
  return {
    ...context,
    denseTable,
    denseQuality,
    denseTableShell,
    csrfCookie,
    denseQuery,
    firstDensePageResponse,
    firstDensePage,
    lastDensePageResponse,
    lastDensePage,
    firstDenseEntity,
    lastDenseEntity,
    crossPageComparisonName,
    createCrossPageComparison,
    crossPageComparison,
    densePagination,
    crossPageAddTrigger,
    crossPagePicker,
    crossPageSetSelect,
    crossPagePickerClose,
    crossPagePickerSubmit,
    crossPageBatchResponse,
    crossPageBatch,
    createEntity,
    draftEntity,
    createdEntity,
    companyName,
    createCompany,
    draftCompany,
    createdCompany,
    entityLandscape,
    entityTypeStats,
    savedLandscapeName,
    savedLandscapeDialog,
    savedLandscapeRow,
    replayedEntityLandscape,
  };
}
