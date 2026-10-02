import { expect } from "@playwright/test";
import { readBrowserQualityMetrics } from "../helpers";
import type { verifyQueryCancellationAndPagination } from "./query-cancellation-and-pagination";

type DenseVisualContext = Pick<
  Awaited<ReturnType<typeof verifyQueryCancellationAndPagination>>,
  "page" | "testInfo" | "paginationQuery"
>;

export async function verifyDenseResultsVisual({ page, testInfo, paginationQuery }: DenseVisualContext) {
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  const denseTable = page.getByRole("table", { name: "实体检索结果" });
  await expect(denseTable).toBeVisible();
  await expect(page.getByRole("navigation", { name: "实体检索结果分页" }).getByText("共 205 条")).toBeVisible();
  await denseTable.locator("th").filter({ hasText: "名称" }).first().getByRole("button").click();
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
  await expect(denseTable.locator('th[aria-sort="ascending"]')).toContainText("名称");
  const denseQuality = await readBrowserQualityMetrics(page);
  testInfo.annotations.push({ type: "dense-results-quality-metrics", description: JSON.stringify(denseQuality) });
  expect(denseQuality.lcp_ms).toBeGreaterThan(0);
  expect(denseQuality.lcp_ms).toBeLessThanOrEqual(2_500);
  expect(denseQuality.interaction_count).toBeGreaterThan(0);
  expect(denseQuality.inp_ms).toBeLessThanOrEqual(200);
  expect(denseQuality.cls).toBeLessThanOrEqual(0.1);
  const denseTableShell = page.locator(".virtual-table-shell").filter({ has: denseTable });
  await expect(denseTableShell).toHaveCount(1);
  // Keep the pointer outside the viewport so row hover styling cannot make the
  // repository-owned visual baseline depend on the previous interaction target.
  await page.mouse.move(-10, -10);
  await expect(denseTableShell).toHaveScreenshot("research-dense-results.png", {
    animations: "disabled",
    caret: "hide",
    mask: [denseTableShell.locator(".entity-match-context")],
    maskColor: "#dce4e7",
    maxDiffPixelRatio: 0.001,
  });
  return { denseTable, denseQuality, denseTableShell };
}
