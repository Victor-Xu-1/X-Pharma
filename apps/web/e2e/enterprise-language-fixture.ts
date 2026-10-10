import type { Page } from "@playwright/test";
import type { EnterpriseOverviewRead, UserGroupRead } from "../src/lib/generated";
import { installGovernanceFixture } from "./governance-fixture";

const time = "2026-10-11T00:00:00Z";
const overview: EnterpriseOverviewRead = {
  tenant: {
    id: "controlled-tenant",
    slug: "original-organization",
    name: "Original organization <source>",
    active: true,
    created_at: time,
    updated_at: time,
  },
  user_count: 1,
  active_user_count: 1,
  admin_count: 1,
  group_count: 0,
  active_group_count: 0,
  dataset_count: 0,
  active_source_count: 0,
  audit_event_count_24h: 0,
};
/** Every enterprise write is fulfilled in the browser, never by the live identity service. */
export async function installEnterpriseLanguageFixture(page: Page) {
  const base = await installGovernanceFixture(page);
  const state = {
    groups: [] as UserGroupRead[],
    reads: 0,
    writes: [] as unknown[],
    hold: false,
    fail: false,
    release: undefined as (() => void) | undefined,
  };
  await page.route("**/api/v1/enterprise/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (request.method() === "GET") {
      state.reads++;
      if (path === "/api/v1/enterprise/overview") return route.fulfill({ json: overview });
      if (path === "/api/v1/enterprise/groups") return route.fulfill({ json: state.groups });
      if (
        path === "/api/v1/enterprise/account-invitations" ||
        path === "/api/v1/enterprise/users" ||
        path === "/api/v1/enterprise/llm-providers"
      )
        return route.fulfill({ json: [] });
    }
    if (request.method() === "POST" && path === "/api/v1/enterprise/groups") {
      const payload = request.postDataJSON();
      state.writes.push(payload);
      if (state.hold)
        await new Promise<void>((resolve) => {
          state.release = resolve;
        });
      if (state.fail) return route.fulfill({ status: 503, json: { detail: "RAW_CONTROLLED_GROUP_FAILURE" } });
      const group: UserGroupRead = {
        id: "controlled-group",
        tenant_id: "controlled-tenant",
        name: payload.name,
        description: payload.description,
        active: true,
        version: 1,
        member_ids: [],
        member_count: 0,
        created_at: time,
        updated_at: time,
      };
      state.groups = [group];
      return route.fulfill({ json: group });
    }
    throw new Error("Unexpected enterprise fixture request: " + request.method() + " " + path);
  });
  return { base, state };
}
