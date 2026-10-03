import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";
import type { EnterpriseApiKeyCatalogRead } from "../../src/lib/generated";

export async function verifyEnterpriseAdministration({
  page,
}: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const users = [
    {
      id: "browser-admin",
      tenant_id: "browser-tenant",
      email: "browser-admin@example.test",
      display_name: "Browser Admin",
      role: "admin",
      active: true,
      token_version: 1,
      last_login_at: "2026-07-19T10:00:00Z",
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-19T10:00:00Z",
    },
    {
      id: "browser-analyst",
      tenant_id: "browser-tenant",
      email: "browser-analyst@example.test",
      display_name: "Browser Analyst",
      role: "analyst",
      active: true,
      token_version: 4,
      last_login_at: null,
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-19T10:00:00Z",
    },
  ];
  const roleUpdates: Array<Record<string, unknown>> = [];
  const sessionRevocations: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-admin",
          tenant_id: "browser-tenant",
          email: "browser-admin@example.test",
          display_name: "Browser Admin",
          role: "admin",
        },
      });
    }
    if (path === "/api/v1/enterprise/overview") {
      return route.fulfill({
        json: {
          tenant: {
            id: "browser-tenant",
            slug: "browser",
            name: "Browser Pharma Tenant",
            active: true,
            created_at: "2026-07-01T00:00:00Z",
            updated_at: "2026-07-19T10:00:00Z",
          },
          user_count: 2,
          active_user_count: 2,
          admin_count: 1,
          group_count: 1,
          active_group_count: 1,
          dataset_count: 5,
          active_source_count: 3,
          audit_event_count_24h: 8,
        },
      });
    }
    if (path === "/api/v1/enterprise/platform") {
      return route.fulfill({
        json: {
          generated_at: "2026-07-25T12:00:00Z",
          environment: "test",
          services: [
            {
              service_id: "api",
              owner: "platform-operations",
              escalation_policy: "role://platform-operations/on-call",
              status: "ready",
              detail: "Current authenticated API request completed",
            },
            {
              service_id: "mcp",
              owner: "platform-operations",
              escalation_policy: "role://platform-operations/on-call",
              status: "external",
              detail: "Dedicated Agent entry probe required",
            },
          ],
          queues: {
            ingestion: { pending: 1, running: 1, stale: 0 },
            outbox: { pending: 0, failed: 0 },
            deliveries: { opensearch: { retry: 0, dead: 0 } },
            governance: { review_pending: 2 },
          },
          workflow: {
            engine: "temporal",
            enabled: true,
            namespace: "default",
            task_queue: "pharma-data-factory",
            max_concurrent_activities: 20,
          },
          model_budget: {
            window: "24h",
            run_count: 2,
            input_tokens: 400,
            output_tokens: 100,
            estimated_cost: "0.020000",
            failed_runs: 0,
            max_document_cost: "2.000000",
            provider: "remote_api",
            model: "mimo-v2.5",
          },
          slos: [
            {
              id: "web-availability",
              service: "api",
              metric: "http.server.duration",
              measurement: "success_ratio",
              target: 0.999,
              window: "30d",
              evaluation_status: "external_evidence_required",
              error_budget_policy: "freeze_noncritical_changes",
            },
          ],
          alerts: [],
          migration: {
            current_revision: "fc5e8a1b3d72",
            expected_revision: "fc5e8a1b3d72",
            status: "current",
          },
          evidence: [
            {
              category: "backup_restore",
              status: "passed",
              artifact: "backup_restore/report.json",
              sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              observed_at: "2026-07-25T11:00:00Z",
              detail: "Machine report status: passed",
            },
            {
              category: "release_candidate",
              status: "missing",
              artifact: "candidate-summary.json",
              sha256: null,
              observed_at: null,
              detail: "No machine-generated evidence is mounted",
            },
            {
              category: "production_topology",
              status: "not_configured",
              artifact: "production_topology/report.json",
              sha256: null,
              observed_at: null,
              detail: "Evidence mount is not configured for this environment",
            },
          ],
          recent_events: [],
        },
      });
    }
    if (path === "/api/v1/enterprise/users" && request.method() === "GET") return route.fulfill({ json: users });
    if (path === "/api/v1/enterprise/api-keys" && request.method() === "GET") {
      const catalog = {
        items: [],
        required_scope: "mcp:connect",
        allowed_scopes: ["mcp:connect", "entities:read", "targets:read"],
        min_ttl_hours: 1,
        max_ttl_days: 366,
      } satisfies EnterpriseApiKeyCatalogRead;
      return route.fulfill({ json: catalog });
    }
    if (path === "/api/v1/enterprise/datasets") {
      return route.fulfill({
        json: [
          {
            id: "browser-dataset",
            dataset_key: "literature",
            display_name: "Browser literature dataset",
            active: true,
            version: 3,
            required_scopes: ["evidence:read"],
            license_id: "browser-license",
            license_policy_version: "browser-v1",
            permitted_channels: ["web", "mcp"],
            license_current: true,
            attribution: "Browser controlled fixture",
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/sessions" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "browser-remote-session",
            user_id: "browser-analyst",
            user_display_name: "Browser Analyst",
            user_email: "browser-analyst@example.test",
            issued_at: "2026-07-19T09:00:00Z",
            expires_at: "2099-07-19T17:00:00Z",
            revoked_at: null,
            revoked_by_user_id: null,
            revoke_reason: null,
            current: false,
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/sessions/browser-remote-session/revoke" && request.method() === "POST") {
      sessionRevocations.push(request.postDataJSON() as Record<string, unknown>);
      return route.fulfill({
        json: {
          id: "browser-remote-session",
          user_id: "browser-analyst",
          user_display_name: "Browser Analyst",
          user_email: "browser-analyst@example.test",
          issued_at: "2026-07-19T09:00:00Z",
          expires_at: "2099-07-19T17:00:00Z",
          revoked_at: "2026-07-19T10:00:00Z",
          revoked_by_user_id: "browser-admin",
          revoke_reason: "Browser remote session revocation",
          current: false,
        },
      });
    }
    if (path === "/api/v1/commercial/clients") return route.fulfill({ json: [] });
    if (path === "/api/v1/commercial/data-lifecycle/retention-policies") return route.fulfill({ json: [] });
    if (path === "/api/v1/commercial/data-lifecycle/legal-holds") return route.fulfill({ json: [] });
    if (path === "/api/v1/enterprise/groups") {
      return route.fulfill({
        json: [
          {
            id: "browser-group",
            tenant_id: "browser-tenant",
            name: "Research Operations",
            description: "Browser acceptance group",
            active: true,
            version: 2,
            member_ids: ["browser-analyst"],
            member_count: 1,
            created_at: "2026-07-01T00:00:00Z",
            updated_at: "2026-07-19T10:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/users/browser-analyst/role" && request.method() === "POST") {
      roleUpdates.push(request.postDataJSON() as Record<string, unknown>);
      return route.fulfill({ json: { ...users[1], role: "admin", token_version: 5 } });
    }
    if (path === "/api/v1/enterprise/audit-events") return route.fulfill({ json: { items: [], next_cursor: null } });
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/internal?view=enterprise");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByRole("heading", { name: "企业账户与审计" })).toBeVisible();
  await expect(page.getByText("Browser Pharma Tenant", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "用户与角色" }).click();
  await expect(page.getByRole("button", { name: "调整 Browser Admin 的角色" })).toBeDisabled();
  await page.getByRole("button", { name: "调整 Browser Analyst 的角色" }).click();
  await page.getByLabel("新角色").selectOption("admin");
  await page.getByLabel("变更原因").fill("Browser acceptance role governance");
  await page.getByRole("button", { name: "确认变更" }).click();
  await expect.poll(() => roleUpdates.length).toBe(1);
  expect(roleUpdates[0]).toEqual({
    expected_token_version: 4,
    role: "admin",
    reason: "Browser acceptance role governance",
  });
  await page.getByRole("tab", { name: "访问与生命周期" }).click();
  await expect(page.getByRole("heading", { name: "数据集与交付授权" })).toBeVisible();
  await expect(page.getByText("WEB / MCP", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "撤销", exact: true }).click();
  await page.getByLabel("变更原因").fill("Browser remote session revocation");
  await page.getByRole("button", { name: "确认变更" }).click();
  await expect.poll(() => sessionRevocations.length).toBe(1);
  expect(sessionRevocations[0]).toEqual({ reason: "Browser remote session revocation" });
  await page.getByRole("tab", { name: "平台运营" }).click();
  await expect(page.getByRole("table", { name: "平台服务状态" })).toContainText("platform-operations");
  await expect(page.getByRole("table", { name: "平台 SLO" })).toContainText("web-availability");
  await expect(page.getByRole("table", { name: "平台发布证据" })).toContainText("backup_restore");
  expect(pageErrors).toEqual([]);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
