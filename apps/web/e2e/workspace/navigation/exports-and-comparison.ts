import { readFile } from "node:fs/promises";
import { expect } from "@playwright/test";
import type { verifyTablePreferencesAndQuickDetail } from "./table-preferences-and-quick-detail";

export async function verifyExportsAndComparison(
  context: Awaited<ReturnType<typeof verifyTablePreferencesAndQuickDetail>>,
) {
  const { page, fixtureKey, fixtureName, csrfCookie, createdEntity, companyName, createdCompany, restoredEntityTable } =
    context;
  await expect(restoredEntityTable.getByRole("columnheader", { name: "外部标识" })).toBeVisible();
  expect(
    (await restoredEntityTable.getByRole("columnheader").allTextContents())
      .map((label) => label.trim())
      .filter(Boolean)
      .slice(0, 2),
  ).toEqual(["名称", "类型"]);
  const domainExport = page.locator("details.domain-export-menu");
  await expect(domainExport).toBeVisible();
  await domainExport.locator("summary").click();
  await expect(domainExport.getByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
  await expect(domainExport.getByRole("checkbox", { name: "名称" })).toBeChecked();
  const exportResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/workspace/domain-exports") && response.request().method() === "POST",
  );
  const domainDownloadPromise = page.waitForEvent("download");
  await domainExport.getByRole("button", { name: "下载" }).click();
  const [exportResponse, domainDownload] = await Promise.all([exportResponsePromise, domainDownloadPromise]);
  expect(exportResponse.status()).toBe(200);
  expect(exportResponse.headers()["x-export-event-id"]).toMatch(/^[0-9a-f-]{36}$/);
  expect(exportResponse.request().postDataJSON()).toMatchObject({
    dataset: "entities",
    query: { q: fixtureKey, entity_types: ["target", "organization"], review_status: "verified" },
    export_format: "json",
    max_records: 2,
  });
  expect(domainDownload.suggestedFilename()).toBe("entities-query.json");
  const downloadedPath = await domainDownload.path();
  if (!downloadedPath) throw new Error("Google Chrome did not persist the governed domain export");
  const exportedDocument = JSON.parse(await readFile(downloadedPath, "utf8")) as {
    schema: string;
    dataset: string;
    query: Record<string, string | string[]>;
    records: Array<Record<string, unknown>>;
  };
  expect(exportedDocument.schema).toBe("pharma.workspace-domain-export.v1");
  expect(exportedDocument.dataset).toBe("entities");
  expect(exportedDocument.query).toEqual({
    q: fixtureKey,
    entity_types: ["target", "organization"],
    review_status: "verified",
  });
  expect(exportedDocument.records).toHaveLength(2);
  expect(exportedDocument.records.map((record) => record.name)).toEqual(
    expect.arrayContaining([fixtureName, companyName]),
  );
  const comparisonName = `Browser result list ${fixtureKey}`;
  const createComparison = await page.request.post("/api/v1/comparison-sets", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: { name: comparisonName, visibility: "private" },
  });
  expect(createComparison.status()).toBe(201);
  const comparison = (await createComparison.json()) as { id: string; version: number };
  await page.getByRole("checkbox", { name: `选择对比 ${fixtureName}` }).click();
  await page.getByRole("checkbox", { name: `选择对比 ${companyName}` }).click();
  await expect(page.getByText("已选 2/20 项", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "加入列表" }).click();
  const comparisonPicker = page.getByRole("dialog", { name: "加入对比列表" });
  await expect(comparisonPicker.getByLabel("目标列表")).toHaveValue(comparison.id);
  await expect(comparisonPicker.getByText("完成后共 2/20 个实体", { exact: true })).toBeVisible();
  const comparisonBatchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/comparison-sets/${comparison.id}/members/batch`) &&
      response.request().method() === "POST",
  );
  await comparisonPicker.getByRole("button", { name: "确认加入" }).click();
  const batchResponse = await comparisonBatchResponse;
  expect(batchResponse.status()).toBe(200);
  expect(batchResponse.request().postDataJSON()).toEqual({
    entity_ids: [createdEntity.id, createdCompany.id],
    expected_version: 1,
  });
  await expect(page.getByText(`2 个实体已加入 ${comparisonName}`, { exact: true })).toBeVisible();
  await page.goto("/workspace/research?view=collections");
  const comparisonTable = page.locator(".comparison-table");
  await expect(comparisonTable.getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText(companyName, { exact: true })).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.get("collection")).toBe(comparison.id);
  await page.getByRole("checkbox", { name: `纳入情报对比：${fixtureName}` }).check();
  await page.getByRole("checkbox", { name: `纳入情报对比：${companyName}` }).check();
  await expect
    .poll(() => new URL(page.url()).searchParams.get("compare"))
    .toBe(`${createdEntity.id},${createdCompany.id}`);
  const dossierMatrix = page.getByRole("table", { name: "研发情报对比表" });
  await expect(dossierMatrix).toBeVisible();
  await expect(dossierMatrix.getByRole("columnheader", { name: new RegExp(fixtureName) })).toBeVisible();
  await expect(dossierMatrix.getByRole("columnheader", { name: new RegExp(companyName) })).toBeVisible();
  await expect(dossierMatrix.getByRole("rowheader", { name: "查询时间" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: `纳入情报对比：${fixtureName}` })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: `纳入情报对比：${companyName}` })).toBeChecked();
  await expect(dossierMatrix).toBeVisible();
  await dossierMatrix.getByRole("button", { name: `打开 ${fixtureName} 详情` }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("entity")).toBe(createdEntity.id);
  await page.goBack();
  await expect(dossierMatrix).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.goBack();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  return {
    ...context,
    domainExport,
    exportResponsePromise,
    domainDownloadPromise,
    exportResponse,
    domainDownload,
    downloadedPath,
    exportedDocument,
    comparisonName,
    createComparison,
    comparison,
    comparisonPicker,
    comparisonBatchResponse,
    batchResponse,
    comparisonTable,
    dossierMatrix,
  };
}
