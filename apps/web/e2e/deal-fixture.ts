import type { Page } from "@playwright/test";
import { dealResult } from "../src/test/fixtures/dealResearch";

export async function installDealFixture(page: Page) {
  const state = {
    reads: 0,
    lastUpfrontMinimum: null as string | null,
    organizationReads: 0,
    organizationStatus: 503,
    writes: [] as string[],
    errors: [] as string[],
  };
  const terms = {
    royalty: { lower: 0, contingent: false, clauses: ["原始条款 <License>", { region: "SOURCE_REGION" }] },
  };
  const deal = {
    ...dealResult.items[0],
    name: "CONTROLLED FIXTURE · 原始交易 EGFR",
    upfront_amount: 0.000123456,
    total_potential_amount: 25123456.75,
    terms,
  };
  page.on("pageerror", (error) => state.errors.push(error.message));
  // Browser-only controlled responses: never ingestion inputs or authoritative data.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      state.writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/workspace/table-preferences/deals")
      return route.fulfill({
        json: {
          preference_key: "deals",
          schema_version: 1,
          column_order: [],
          column_visibility: {},
          density: "comfortable",
          version: 0,
          persisted: false,
          updated_at: null,
        },
      });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-deal-user",
          tenant_id: "controlled-deal-tenant",
          email: "deal-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/deal-transactions") {
      state.reads++;
      state.lastUpfrontMinimum = new URL(request.url()).searchParams.get("upfront_amount_min");
      return route.fulfill({ json: { ...dealResult, items: [deal], total: 1 } });
    }
    if (path === `/api/v1/deal-transactions/${deal.id}`) {
      state.reads++;
      return route.fulfill({ json: deal });
    }
    if (path === "/api/v1/entities") {
      state.organizationReads++;
      if (state.organizationStatus !== 200)
        return route.fulfill({ status: state.organizationStatus, json: { detail: "RAW_ORGANIZATION_FAILURE" } });
      return route.fulfill({
        json: {
          query_schema_version: "pharma.entity.search.v2",
          applied_filters: [],
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          sort_by: "relevance",
          sort_direction: "desc",
          engine: "opensearch",
          facets: {},
          suggestions: [],
          took_ms: 0,
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });
  return { state, deal, terms };
}
