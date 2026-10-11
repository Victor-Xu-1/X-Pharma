import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo } from "@playwright/test";
import type { CompanyDossier } from "../src/lib/contracts/company";
import { genericDossierIdentityFixture } from "./generic-dossier-identity";

/** Response-controlled browser setup shared by independent bounded journeys. */
export async function installCompanyBrowserFixture(page: Page, testInfo: TestInfo, data: CompanyDossier) {
  const genericIdentity = genericDossierIdentityFixture(data);
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
    if (path === `/api/v1/entities/${data.entity.id}`) return route.fulfill({ json: data.entity });
    const genericReply = genericIdentity.response(path);
    if (genericReply) return route.fulfill(genericReply);
    if (path === `/api/v1/companies/${data.entity.id}/dossier`) {
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
  return { genericIdentity, errors, writes, audit, dossierReads: () => dossierReads };
}
