import { expect, type Page } from "@playwright/test";
import type { CompanyDossier } from "../src/lib/contracts/company";
import { selectInterfaceLanguage } from "./interface-language";

/** Controlled response boundaries; no extra test registrations or service writes. */
export function genericCompanyIdentityFixture(data: CompanyDossier) {
  let dossierMode: "valid" | "id" | "type" = "valid";
  let timelineMode: "valid" | "foreign" = "valid";
  const entityId = data.entity.id;
  const errorCaptions = {
    en: {
      dossier: "Entity dossier does not match the requested identity",
      timeline: "Organization timeline does not match the requested identity",
      retry: "Retry",
    },
    "zh-CN": { dossier: "领域档案与请求实体不一致", timeline: "公司时间线与请求实体不一致", retry: "重试" },
  } as const;

  function response(path: string) {
    if (path === `/api/v1/entities/${entityId}/dossier`)
      return {
        json: {
          ...data,
          entity: {
            ...data.entity,
            id: dossierMode === "id" ? "00000000-0000-4000-b000-000000000099" : entityId,
            entity_type: dossierMode === "type" ? "drug" : data.entity.entity_type,
            name: dossierMode === "valid" ? data.entity.name : "FOREIGN DOSSIER IDENTITY",
          },
        },
      };
    if (path === `/api/v1/companies/${entityId}/timeline`)
      return {
        json:
          timelineMode === "valid"
            ? data.timeline
            : {
                ...data.timeline,
                company: { ...data.entity, id: "00000000-0000-4000-b000-000000000098" },
                total: 913,
                items: [
                  {
                    id: "foreign-event",
                    event_type: "program_status",
                    occurred_at: "2026-07-01T00:00:00Z",
                    title: "FOREIGN TIMELINE EVENT",
                    program: null,
                    deal: null,
                  },
                ],
              },
      };
    return null;
  }

  async function verify(page: Page, audit: (name: string) => Promise<void>) {
    const route = `/workspace/research?view=entity&entity=${entityId}&section=company_intelligence`;
    for (const mismatch of ["id", "type"] as const) {
      dossierMode = mismatch;
      await page.goto(route);
      const originalUrl = page.url();
      for (const locale of ["en", "zh-CN"] as const) {
        await selectInterfaceLanguage(page, locale);
        await expect(page.getByText(errorCaptions[locale].dossier, { exact: true })).toBeVisible();
        await expect(page.getByRole("heading", { name: "FOREIGN DOSSIER IDENTITY", exact: true })).toHaveCount(0);
        await expect(page.locator(".entity-dossier-page")).toHaveCount(0);
        expect(page.url()).toBe(originalUrl);
      }
      dossierMode = "valid";
      await page.getByRole("button", { name: errorCaptions["zh-CN"].retry, exact: true }).click();
      await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
      await expect(page.locator("#entity-dossier-tab-company_intelligence")).toHaveAttribute("aria-selected", "true");
    }
    await selectInterfaceLanguage(page, "en");
    timelineMode = "foreign";
    await page.reload();
    for (const locale of ["en", "zh-CN"] as const) {
      await selectInterfaceLanguage(page, locale);
      await expect(page.getByText(errorCaptions[locale].timeline, { exact: true })).toBeVisible();
      await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
      await expect(page.getByText("FOREIGN TIMELINE EVENT", { exact: true })).toHaveCount(0);
      await expect(page.locator(".company-intelligence-metrics")).not.toContainText("913");
      await expect(page.locator(".company-intelligence-metrics > div").nth(3).locator("dd")).toHaveText("--");
    }
    await audit("generic-company-foreign-timeline-zh");
    timelineMode = "valid";
    await page.getByRole("button", { name: errorCaptions["zh-CN"].retry, exact: true }).click();
    await expect(page.getByText(errorCaptions["zh-CN"].timeline, { exact: true })).toHaveCount(0);
    await expect(page.locator(".company-intelligence-metrics > div").nth(2).locator("dd")).toHaveText(
      String(data.timeline.total),
    );
    await audit("generic-company-corrected-timeline-zh");
  }
  return { response, verify };
}
