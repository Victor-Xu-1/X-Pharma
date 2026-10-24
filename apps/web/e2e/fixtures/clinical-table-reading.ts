import { expect, type Page, type Route, type TestInfo } from "@playwright/test";
import { trialResult } from "../../src/test/fixtures/clinicalTrial";
import { selectInterfaceLanguage } from "../interface-language";
import { linkedTrialProgramDisclosure } from "./clinical-disclosure";

/** Reuse the synthetic UI study; no real records or preference writes. */
export async function expectClinicalTableReading(page: Page, testInfo: TestInfo) {
  let savedOrder: string[] = [];
  let reads = 0;
  const writes: string[] = [];
  const preferences = "/api/v1/workspace/table-preferences/clinical-trials";
  const matches = (url: URL) => url.pathname === "/api/v1/trials" || url.pathname === preferences;
  const respond = (route: Route) => {
    const request = route.request();
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(request.method());
      return route.abort("blockedbyclient");
    }
    if (new URL(request.url()).pathname === "/api/v1/trials") {
      reads++;
      return route.fulfill({ json: { ...trialResult, total: 1, offset: 0, applied_filters: {} } });
    }
    return route.fulfill({
      json: {
        preference_key: "clinical-trials",
        schema_version: 1,
        column_order: savedOrder,
        column_visibility: {},
        density: "comfortable",
        version: 1,
        persisted: true,
        updated_at: null,
      },
    });
  };
  await page.route(matches, respond);
  try {
    await page.goto("/workspace/research?view=trials");
    const table = page.getByRole("table", { name: "Clinical trial results", exact: true });
    await expect(table).toContainText(trialResult.items[0].registry_id);
    const headers = await table.getByRole("columnheader").allTextContents();
    const position = (label: string) => headers.findIndex((header) => header.startsWith(label));
    expect(position("Phase")).toBeGreaterThanOrEqual(0);
    expect(position("Status")).toBeGreaterThanOrEqual(0);
    expect(position("Study acronym")).toBeGreaterThanOrEqual(0);
    expect(position("Phase")).toBeLessThan(position("Study acronym"));
    expect(position("Status")).toBeLessThan(position("Study acronym"));
    const viewport = page.viewportSize();
    if (viewport && viewport.width >= 1440) {
      await expect(table.getByText(trialResult.items[0].registry_id, { exact: true })).toBeInViewport({ ratio: 1 });
    }
    await page.screenshot({ path: testInfo.outputPath("clinical-table-default-en.png"), animations: "disabled" });
    const form = page.getByRole("form", { name: "Clinical trial filters", exact: true });
    const linked = linkedTrialProgramDisclosure(page, form, "Linked drug attributes");
    await expect(linked).toHaveCount(1);
    await expect(linked).not.toHaveAttribute("open", "");
    await linked.locator(":scope > summary").click();
    await expect(linked).toHaveAttribute("open", "");
    await expect(linked.getByText("Within the same drug program", { exact: true })).toBeVisible();
    await linked.locator(":scope > summary").click();
    await expect(linked).not.toHaveAttribute("open", "");
    const cachedReads = reads;
    await selectInterfaceLanguage(page, "zh-CN");
    await expect(page.getByRole("table", { name: "临床试验结果", exact: true })).toContainText(
      trialResult.items[0].registry_id,
    );
    const chineseForm = page.getByRole("form", { name: "临床试验筛选", exact: true });
    const chineseLinked = linkedTrialProgramDisclosure(page, chineseForm, "关联药物属性");
    await expect(chineseLinked).toHaveCount(1);
    await expect(chineseLinked).not.toHaveAttribute("open", "");
    expect(reads).toBe(cachedReads);
    await selectInterfaceLanguage(page, "en");
    savedOrder = ["registry_id", "acronym", "overall_status", "phases"];
    await page.reload();
    await expect(table).toContainText(trialResult.items[0].registry_id);
    await expect
      .poll(async () => (await table.getByRole("columnheader").allTextContents()).filter(Boolean).slice(0, 4))
      .toEqual([
        expect.stringMatching(/^Registry/),
        expect.stringMatching(/^Study acronym/),
        expect.stringMatching(/^Status/),
        expect.stringMatching(/^Phase/),
      ]);
    await page.screenshot({ path: testInfo.outputPath("clinical-table-saved-order-en.png"), animations: "disabled" });
    expect(writes).toEqual([]);
  } finally {
    await page.unroute(matches, respond);
  }
}
