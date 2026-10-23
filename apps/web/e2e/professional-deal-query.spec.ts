import { expect, test } from "@playwright/test";
import { dealResult } from "../src/test/fixtures/dealResearch";
import { installDealFixture } from "./deal-fixture";
import { selectInterfaceLanguage } from "./interface-language";
import { verifyProfessionalDealQuery } from "./workspace/navigation/professional-deal-query";

test("[professional-deal-query] submits the complete currency-scoped query and restores the normalized participant", async ({
  page,
}) => {
  const { state, deal } = await installDealFixture(page);
  const company = {
    ...deal.party_entities[0],
    aliases: [],
    canonical_name: "Acme Pharma",
    external_ids: {},
    description: null,
    attributes: {},
    status: "active",
  };
  await page.route(/\/api\/v1\/entities(?:\/[^/?]+)?(?:\?.*)?$/, (route) => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({
      json:
        path === "/api/v1/entities"
          ? {
              query_schema_version: "pharma.entity.search.v2",
              applied_filters: [],
              items: [company],
              total: 1,
              limit: 100,
              offset: 0,
              sort_by: "relevance",
              sort_direction: "desc",
              engine: "opensearch",
              facets: {},
              suggestions: [],
              took_ms: 0,
              warnings: [],
            }
          : company,
    });
  });
  await page.route(/\/api\/v1\/deal-transactions(?:\?.*)?$/, (route) => {
    const parameters = new URL(route.request().url()).searchParams;
    return route.fulfill({
      json: {
        ...dealResult,
        items: [deal],
        applied_filters: [...parameters]
          .filter(([field]) =>
            ["q", "status", "party_role", "development_phase_at_transaction", "currency"].includes(field),
          )
          .map(([field, value]) => ({ field, value, operator: "eq" })),
      },
    });
  });
  await page.goto("/workspace/research?view=deals");
  await selectInterfaceLanguage(page, "zh-CN");
  await verifyProfessionalDealQuery({ page, companyName: company.name, createdCompany: company });
  await expect(page).toHaveURL(/currency=USD/);
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});
