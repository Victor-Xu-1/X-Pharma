import { expect, type Page } from "@playwright/test";
import type { CompanyDossier } from "../src/lib/contracts/company";
import { selectInterfaceLanguage } from "./interface-language";

/** Controlled response boundaries; no extra test registrations or service writes. */
export function genericDossierIdentityFixture(data: CompanyDossier) {
  let dossierMode: "valid" | "id" | "type" = "valid";
  let legacyCompanyReads = 0;
  const entityId = "00000000-0000-4000-a000-000000000097";
  // Only a non-specialized entity reaches EntityDossierView in the actual route model.
  const entity = {
    ...data.entity,
    id: entityId,
    canonical_entity_id: entityId,
    entity_type: "patent" as const,
    name: "原始专利实体 / Controlled domain fixture",
    description: "Controlled generic identity, not a real patent",
  };
  const errorCaptions = {
    en: {
      dossier: "Entity dossier does not match the requested identity",
      retry: "Retry",
    },
    "zh-CN": { dossier: "领域档案与请求实体不一致", retry: "重试" },
  } as const;

  function response(path: string) {
    if (path === `/api/v1/entities/${data.entity.id}/dossier`) {
      legacyCompanyReads++;
      return { json: data };
    }
    if (path === `/api/v1/companies/${data.entity.id}/timeline`) {
      legacyCompanyReads++;
      return { json: data.timeline };
    }
    if (path === `/api/v1/entities/${entityId}`) return { json: entity };
    if (path === `/api/v1/entities/${entityId}/dossier`)
      return {
        json: {
          ...data,
          entity: {
            ...entity,
            id: dossierMode === "id" ? "00000000-0000-4000-b000-000000000099" : entityId,
            entity_type: dossierMode === "type" ? "drug" : entity.entity_type,
            name: dossierMode === "valid" ? entity.name : "FOREIGN DOSSIER IDENTITY",
          },
        },
      };
    return null;
  }

  async function verify(page: Page, audit: (name: string) => Promise<void>) {
    const route = `/workspace/research?view=entity&entity=${entityId}&section=relationships`;
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
      await audit(`generic-dossier-${mismatch}-mismatch-zh`);
      dossierMode = "valid";
      await page.getByRole("button", { name: errorCaptions["zh-CN"].retry, exact: true }).click();
      await expect(page.getByRole("heading", { name: entity.name, exact: true })).toBeVisible();
      await expect(page.locator("#entity-dossier-tab-relationships")).toHaveAttribute("aria-selected", "true");
      expect(page.url()).toBe(originalUrl);
      await audit(`generic-dossier-${mismatch}-corrected-zh`);
    }
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
    await expect(page.getByRole("heading", { name: entity.name, exact: true })).toBeVisible();
    await expect(page.locator("#entity-dossier-tab-relationships")).toHaveAttribute("aria-selected", "true");
    // Cached popstate navigation keeps the generic module loaded: it must not start
    // a competing generic organization dossier/timeline before specialization.
    const beforeSpecialization = legacyCompanyReads;
    await page.evaluate((id) => {
      history.pushState(null, "", `/workspace/research?view=entity&entity=${id}&section=overview`);
      dispatchEvent(new PopStateEvent("popstate"));
    }, data.entity.id);
    await expect(page).toHaveURL(new RegExp(`view=company&entity=${data.entity.id}`));
    await expect(page.getByRole("heading", { name: data.entity.name, exact: true })).toBeVisible();
    expect(legacyCompanyReads - beforeSpecialization).toBe(0);
  }
  return { response, verify };
}
