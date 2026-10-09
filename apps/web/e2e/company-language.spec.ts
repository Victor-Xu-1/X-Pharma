import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { CompanyDossier } from "../src/lib/contracts/company";
import { dossier, program } from "../src/test/fixtures/companyDossier";
import { selectInterfaceLanguage } from "./interface-language";

const organizationId = "a8ed0601-cfa5-4d1f-bb82-898a570596da";
const sections = [
  ["overview", "Organization overview", "公司概览"],
  ["pipeline", "Development pipeline", "研发管线"],
  ["timeline", "Organization timeline", "公司时间线"],
  ["deals", "Deals and partnerships", "交易合作"],
  ["relationships", "Related network", "关联网络"],
  ["trials", "Clinical trials", "临床试验"],
  ["patents", "Patents", "专利"],
  ["regulatory", "Regulatory", "监管"],
  ["news", "Organization updates", "公司动态"],
] as const;

/** Synthetic API responses only; these are not a source or an ingestion input. */
function fixture(providerLabel = false): CompanyDossier {
  const entity = {
    ...dossier.entity,
    id: organizationId,
    canonical_entity_id: organizationId,
    name: "原始机构名称 / Controlled browser fixture",
    description: "原始机构说明 — not a real corporate profile",
    attributes: providerLabel
      ? {
          identity_scope: "provider_label",
          label_provider: "ClinicalTrials.gov",
          identity_note: "原始来源身份说明 — controlled browser fixture",
        }
      : dossier.entity.attributes,
  };
  const programs = Array.from({ length: 10 }, (_, index) => ({
    ...program,
    id: `00000000-0000-4000-a000-${String(index + 1).padStart(12, "0")}`,
    organization_entity_id: organizationId,
    organization_name: entity.name,
    drug_entity_id: `00000000-0000-4000-b000-${String(index + 1).padStart(12, "0")}`,
    drug_name: `SOURCE_ASSET_${index} / 原始研发资产名称 — controlled browser fixture with a complete long name`,
  }));
  programs.push({ ...programs[0], id: "00000000-0000-4000-a000-000000000011", phase: "phase_3" });
  return {
    ...dossier,
    entity,
    programs: providerLabel ? [] : programs,
    summary: {
      ...dossier.summary,
      highest_phase: "phase_3",
      program_count: providerLabel ? 0 : 11,
      drug_count: providerLabel ? 0 : 10,
      phase_distribution: providerLabel ? {} : { phase_2: 10, phase_3: 1 },
    },
    timeline: { ...dossier.timeline, company: entity, items: [] },
    coverage: [{ domain: "programs", total: 11, returned: 11, status: "available", note: "原始覆盖说明" }],
  };
}

for (const providerLabel of [false, true]) {
  test(`[company-language] ${providerLabel ? "registry sponsor" : "canonical organization"} retains identity, sections and loaded assets across language changes`, async ({
    page,
  }, testInfo) => {
    const data = fixture(providerLabel);
    let dossierReads = 0;
    const errors: string[] = [];
    const writes: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", (route) => {
      const request = route.request(),
        path = new URL(request.url()).pathname;
      if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
      if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
        writes.push(`${request.method()} ${path}`);
        return route.abort("blockedbyclient");
      }
      if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
      if (path === "/api/v1/auth/me")
        return route.fulfill({
          json: {
            id: "controlled-company-user",
            tenant_id: "controlled-company-tenant",
            email: "company-language@example.test",
            display_name: "Controlled browser fixture",
            role: "analyst",
          },
        });
      if (path === `/api/v1/entities/${organizationId}`) return route.fulfill({ json: data.entity });
      if (path === `/api/v1/companies/${organizationId}/dossier`) {
        dossierReads++;
        return route.fulfill({ json: data });
      }
      return route.fulfill({ json: [] });
    });

    async function audit(name: string) {
      await page.evaluate(() => window.scrollTo(0, 0));
      expect(
        (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
      ).toEqual([]);
      const bounds = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        document: document.documentElement.scrollWidth,
      }));
      expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
      expect(errors).toEqual([]);
      await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false, animations: "disabled" });
    }

    await page.goto(`/workspace/research?view=company&entity=${organizationId}&section=overview`);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
    if (providerLabel) {
      await expect(page.getByText("Registry sponsor name", { exact: true })).toBeVisible();
      await expect(page.getByText("原始来源身份说明 — controlled browser fixture", { exact: true })).toBeVisible();
      await expect(page.getByText("Highest phase", { exact: true })).toHaveCount(0);
    } else {
      await expect(page.getByText(data.entity.description ?? "", { exact: true })).toBeVisible();
      const assets = page.getByRole("list", { name: "Loaded development assets", exact: true }).first();
      await expect(assets).toContainText("Phase II");
      await expect(assets).toContainText("Phase III");
      await page.getByText("More loaded assets (2)", { exact: true }).click();
      await expect(page.getByRole("button", { name: data.programs[9].drug_name, exact: true })).toBeVisible();
      const originalUrl = page.url();
      await selectInterfaceLanguage(page, "zh-CN");
      expect(page.url()).toBe(originalUrl);
      await expect(page.locator(".company-assets-disclosure")).toHaveAttribute("open", "");
      await expect(page.getByRole("button", { name: data.programs[9].drug_name, exact: true })).toBeVisible();
      await audit("company-complete-assets-zh");
      await selectInterfaceLanguage(page, "en");
      await audit("company-complete-assets-en");
      await page
        .locator(".company-assets-disclosure")
        .locator("..")
        .screenshot({
          path: testInfo.outputPath("company-complete-asset-portfolio-en.png"),
          animations: "disabled",
        });
    }

    for (const [section, english, chinese] of sections) {
      await page.getByRole("tab", { name: english, exact: true }).click();
      await expect(page.getByRole("tab", { name: english, exact: true })).toHaveAttribute("aria-selected", "true");
      await expect(page.getByRole("tabpanel")).toBeVisible();
      const originalUrl = page.url();
      await audit(`company-${section}-en`);
      await selectInterfaceLanguage(page, "zh-CN");
      await expect(page.getByRole("tab", { name: chinese, exact: true })).toHaveAttribute("aria-selected", "true");
      expect(page.url()).toBe(originalUrl);
      await audit(`company-${section}-zh`);
      await selectInterfaceLanguage(page, "en");
    }
    expect(dossierReads).toBe(1);
    await selectInterfaceLanguage(page, "zh-CN");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
    await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "公司动态", exact: true })).toHaveAttribute("aria-selected", "true");
    expect(writes).toEqual([]);
    expect(errors).toEqual([]);
  });
}
