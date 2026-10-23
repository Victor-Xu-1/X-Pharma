import type { Page } from "@playwright/test";
import type { WorkspaceTablePreferenceKey } from "../../src/lib/contracts/workspacePreferences";

/** A complete read-only preference response for isolated page fixtures. */
export async function installReadOnlyTablePreference(page: Page, key: WorkspaceTablePreferenceKey) {
  await page.route(`**/api/v1/workspace/table-preferences/${key}`, (route) => {
    // Unexpected writes still reach the owning fixture's write rejection/log.
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: {
        preference_key: key,
        schema_version: 1,
        column_order: [],
        column_visibility: {},
        density: "comfortable",
        version: 0,
        persisted: false,
        updated_at: null,
      },
    });
  });
}
