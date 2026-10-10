import type { Page } from "@playwright/test";
import { installCommercialFixture } from "./commercial-fixture";
import { controlledRetentionPolicy, controlledSourceAsset } from "./commercial-lifecycle-fixture";
import {
  recordAccount,
  recordClient,
  recordDelivery,
  recordDispute,
  recordEvent,
  recordExport,
  recordHold,
  recordOverview,
  recordRisk,
} from "./commercial-record-values";

/** Populated metadata is controlled browser evidence, never a seeded live commercial tenant. */
export async function installCommercialRecordFixture(page: Page) {
  const base = await installCommercialFixture(page);
  const state = { reads: 0, writes: [] as string[] };
  const responses: Record<string, unknown> = {
    "/api/v1/commercial/overview": recordOverview,
    "/api/v1/commercial/clients": [recordClient],
    "/api/v1/commercial/billing-accounts": [recordAccount],
    "/api/v1/commercial/billing-deliveries": [recordDelivery],
    "/api/v1/commercial/billing-disputes": [recordDispute],
    "/api/v1/commercial/exports": [recordExport],
    "/api/v1/commercial/risk-events/page": { items: [recordRisk], next_cursor: null, total_items: 1 },
    "/api/v1/commercial/data-lifecycle/retention-policies": [
      { ...controlledRetentionPolicy, active: true },
      {
        ...controlledRetentionPolicy,
        id: "controlled-source-policy",
        data_class: "source_asset_snapshot",
        active: true,
      },
    ],
    "/api/v1/commercial/data-lifecycle/legal-holds": [recordHold],
    "/api/v1/commercial/data-lifecycle/events": [recordEvent],
    "/api/v1/commercial/data-lifecycle/export-candidates": [recordExport],
    "/api/v1/commercial/data-lifecycle/source-candidates": [controlledSourceAsset],
    "/api/v1/commercial/data-lifecycle/source-assets/deleted": [
      {
        id: "controlled-deleted-asset",
        data_source_id: "controlled-source",
        logical_path: "original/deleted <source>.md",
        file_name: "Original deleted <source>.md",
        state: "deleted",
        updated_at: recordOverview.as_of,
      },
    ],
  };
  await page.route("**/api/v1/commercial/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET" && Object.hasOwn(responses, path)) {
      state.reads++;
      return route.fulfill({ json: responses[path] });
    }
    state.writes.push(request.method() + " " + path);
    throw new Error("Unexpected record-inspection request: " + request.method() + " " + path);
  });
  return { base, state };
}
