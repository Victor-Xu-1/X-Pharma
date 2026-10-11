import { expect, type Page } from "@playwright/test";
import type { CompanyDossier } from "../src/lib/contracts/company";
import { dossier as diseaseFixture } from "../src/test/fixtures/diseaseDossier";
import { selectInterfaceLanguage } from "./interface-language";

/** Controlled fixtures only, in an independent original-duration browser journey. */
export async function verifyDossierSummaryHierarchy(
  page: Page,
  companyFixture: CompanyDossier,
  audit: (name: string) => Promise<void>,
) {
  const diseaseId = "550e8400-e29b-41d4-a716-446655440042";
  const company = {
    ...companyFixture,
    summary: { ...companyFixture.summary, highest_phase: "SOURCE_FUTURE_PHASE", latest_activity_at: null },
  };
  const disease = {
    ...diseaseFixture,
    entity: {
      ...diseaseFixture.entity,
      id: diseaseId,
      canonical_entity_id: diseaseId,
      name: "CONTROLLED · 原始疾病 EGFR",
    },
    summary: { ...diseaseFixture.summary, highest_phase: "SOURCE_FUTURE_PHASE", latest_activity_at: null },
  };
  const reads = { company: 0, disease: 0 };
  await page.route(`**/api/v1/entities/${diseaseId}`, (route) => route.fulfill({ json: disease.entity }));
  await page.route(`**/api/v1/companies/${company.entity.id}/dossier`, (route) => {
    reads.company++;
    return route.fulfill({ json: company });
  });
  await page.route(`**/api/v1/diseases/${diseaseId}/dossier`, (route) => {
    reads.disease++;
    return route.fulfill({ json: disease });
  });

  for (const [kind, data] of [
    ["company", company],
    ["disease", disease],
  ] as const) {
    await page.goto(`/workspace/research?view=${kind}&entity=${data.entity.id}&section=overview`);
    await selectInterfaceLanguage(page, "en");
    await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
    const primary = page.locator(".dossier-summary-primary"),
      details = page.locator(".dossier-summary-details");
    await expect(primary.locator(":scope > div")).toHaveCount(3);
    await expect(primary.locator("dd").nth(0)).toHaveText("SOURCE_FUTURE_PHASE");
    await expect(primary.locator("dd").nth(1)).toHaveText(`${data.summary.program_count} / ${data.summary.drug_count}`);
    const tops = await primary
      .locator("dd")
      .evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().top));
    expect(Math.max(...tops) - Math.min(...tops)).toBeLessThanOrEqual(1);
    await expect(details).not.toHaveAttribute("open", "");
    await details.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(details).toHaveAttribute("open", "");
    await expect(details.locator("dl > div")).toHaveCount(3);
    await expect(details.locator("dd").last()).toHaveText("--");
    expect(
      await details.locator("summary").evaluate((node) => node.getBoundingClientRect().height),
    ).toBeGreaterThanOrEqual(44);
    await audit(`${kind}-summary-expanded-en`);
    const originalReads = reads[kind],
      originalUrl = page.url();
    await selectInterfaceLanguage(page, "zh-CN");
    await expect(details).toHaveAttribute("open", "");
    await expect(details.locator("summary")).toHaveText("更多档案指标");
    await expect(primary.locator("dd").nth(0)).toHaveText("SOURCE_FUTURE_PHASE");
    expect(reads[kind]).toBe(originalReads);
    expect(page.url()).toBe(originalUrl);
    await details.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(details).not.toHaveAttribute("open", "");
    await audit(`${kind}-summary-collapsed-zh`);
  }
}
