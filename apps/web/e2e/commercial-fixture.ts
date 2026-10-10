import type { Page } from "@playwright/test";
import type { CommercialClientRead, CommercialOverviewRead, WorkspaceExportPolicyRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";
export const controlledCommercialClient: CommercialClientRead = {
  id: "115a81e1-5555-4444-8888-111111111111",
  client_key: "ORIGINAL_CLIENT_KEY",
  display_name: "原始 Agent <source>",
  active: true,
  active_reservations: 0,
  available_units: "0.000000001",
  billing_account_key: null,
  subscription_key: null,
  subscription_status: null,
  denial_count_24h: 0,
  subjects: [],
  last_policy_event_at: null,
  created_at: "2026-10-10T00:00:00Z",
};
const overview: CommercialOverviewRead = {
  as_of: "2026-10-10T00:00:00Z",
  period_start: "2026-10-10T00:00:00Z",
  subscriptions: [],
  active_client_count: 1,
  open_risk_count: 0,
  pending_export_count: 0,
  dead_billing_delivery_count: 0,
  open_dispute_count: 0,
};
/** Every commercial write is intercepted; no billing or access change reaches the actual service. */
export async function installCommercialFixture(page: Page) {
  const base = await installGovernanceFixture(page);
  const state = {
    reads: 0,
    writes: [] as unknown[],
    hold: false,
    denied: false,
    release: undefined as (() => void) | undefined,
    client: { ...controlledCommercialClient },
    holdPolicy: false,
    policyWrites: [] as unknown[],
    releasePolicy: undefined as (() => void) | undefined,
    policy: null as WorkspaceExportPolicyRead | null,
    policyReads: 0,
  };
  await page.route("**/api/v1/workspace/export-policy", (route) => {
    state.policyReads++;
    return state.policy === null
      ? route.fulfill({ status: 404, json: { detail: "CONTROLLED_POLICY_NOT_CONFIGURED" } })
      : route.fulfill({ json: state.policy });
  });
  await page.route("**/api/v1/admin/workspace-export-policy", async (route) => {
    const payload = route.request().postDataJSON();
    state.policyWrites.push(payload);
    if (state.holdPolicy)
      await new Promise<void>((resolve) => {
        state.releasePolicy = resolve;
      });
    state.policy = {
      ...payload,
      id: "controlled-workspace-policy",
      policy_sha256: "f".repeat(64),
      configured_by_user_id: "controlled-user",
      created_at: overview.as_of,
      updated_at: overview.as_of,
    };
    return route.fulfill({ json: state.policy });
  });
  await page.route("**/api/v1/commercial/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      state.reads++;
      if (path === "/api/v1/commercial/overview") return route.fulfill({ json: overview });
      if (path === "/api/v1/commercial/clients")
        return state.denied
          ? route.fulfill({ status: 403, json: { detail: "RAW_COMMERCIAL_DENIAL" } })
          : route.fulfill({ json: [state.client] });
      throw new Error("Unexpected controlled commercial read: " + path);
    }
    if (request.method() === "POST" && path === "/api/v1/commercial/clients/" + state.client.id + "/status") {
      const payload = request.postDataJSON();
      state.writes.push(payload);
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      state.client = { ...state.client, active: payload.active };
      return route.fulfill({ json: state.client });
    }
    throw new Error("Unexpected controlled commercial write: " + request.method() + " " + path);
  });
  return { base, state };
}
