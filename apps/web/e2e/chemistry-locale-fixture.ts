import type { Page } from "@playwright/test";
import type { ChemistrySearchRead, SavedSearchRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";
/** Browser-only responses; no chemical record, saved query or identity is written to a server. */
export async function installChemistryLocaleFixture(page: Page) {
  const base = await installGovernanceFixture(page);
  const state = {
    reads: [] as unknown[],
    saves: [] as unknown[],
    holdRead: false,
    invalid: false,
    holdSave: false,
    rejectSave: false,
    releaseRead: undefined as (() => void) | undefined,
    releaseSave: undefined as (() => void) | undefined,
  };
  await page.route("**/api/v1/chemistry/search", async (route) => {
    const input = route.request().postDataJSON();
    state.reads.push(input);
    if (state.holdRead)
      await new Promise<void>((resolve) => {
        state.releaseRead = resolve;
      });
    if (state.invalid)
      return route.fulfill({
        status: 422,
        json: { detail: { code: "invalid_smiles", message: "PRIVATE_PARSER_DETAIL" } },
      });
    const output: ChemistrySearchRead = {
      mode: input.mode,
      normalized_query: input.query,
      items: [],
      count: 0,
      as_of: "2026-10-10T00:00:00Z",
      standardization_version: "CONTROLLED_STANDARDIZATION",
      fingerprint_version: "CONTROLLED_FINGERPRINT",
      similarity_threshold: input.mode === "similarity" ? input.threshold : null,
    };
    return route.fulfill({ json: output });
  });
  await page.route("**/api/v1/monitoring/saved-searches", async (route) => {
    if (route.request().method() !== "POST") throw Error("Unexpected saved-search fixture read");
    const input = route.request().postDataJSON();
    state.saves.push(input);
    if (state.holdSave)
      await new Promise<void>((resolve) => {
        state.releaseSave = resolve;
      });
    if (state.rejectSave) return route.fulfill({ status: 503, json: { detail: "RAW_CONTROLLED_SAVE_FAILURE" } });
    const saved: SavedSearchRead = {
      id: "515a81e1-5555-4444-8888-111111111111",
      name: input.name,
      description: "",
      owner_user_id: "controlled-user",
      query_type: "chemistry_search",
      query_version: 1,
      query_json: input.query,
      visibility: input.visibility,
      created_at: "2026-10-10T00:00:00Z",
      updated_at: "2026-10-10T00:00:00Z",
    };
    return route.fulfill({ status: 201, json: saved });
  });
  return { base, state };
}
