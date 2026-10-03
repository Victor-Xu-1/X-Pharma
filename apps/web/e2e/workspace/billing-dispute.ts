import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyBillingDispute({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  let disputeCreated = false;
  const dispute = {
    id: "browser-dispute-1",
    dispute_key: "dispute.browser.0001",
    billing_account_id: "browser-account-1",
    billing_account_key: "account-browser",
    billing_account_name: "Browser Research",
    subscription_id: "browser-subscription-1",
    statement_id: "browser-statement-1",
    statement_key: "statement-browser-2026-07",
    invoice_reference_id: null,
    external_invoice_id: null,
    status: "open",
    category: "usage",
    disputed_units: "2.50000000",
    subject: "Browser metering dispute",
    description: "Validate the browser dispute workflow.",
    opened_by: "browser-admin",
    opened_at: "2026-07-18T10:00:00Z",
    assigned_to: null,
    due_at: "2026-07-23T10:00:00Z",
    overdue: false,
    resolution_code: null,
    resolution_notes: "",
    resolved_by: null,
    resolved_at: null,
    resolution_adjustment_key: null,
    version: 1,
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  const posts: Array<{ path: string; body: Record<string, unknown> }> = [];
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
    if (path === "/api/v1/commercial/overview") {
      return route.fulfill({
        json: { as_of: "2026-07-18T10:00:00Z", period_start: "2026-07-18T00:00:00Z", subscriptions: [] },
      });
    }
    if (path === "/api/v1/commercial/billing-deliveries") {
      return route.fulfill({
        json: [
          {
            delivery_id: null,
            event_id: "browser-event-1",
            statement_id: dispute.statement_id,
            statement_key: dispute.statement_key,
            billing_account_id: dispute.billing_account_id,
            billing_account_key: dispute.billing_account_key,
            billing_account_name: dispute.billing_account_name,
            state: "pending",
            attempts: 0,
            available_at: "2026-07-18T10:00:00Z",
            lease_expires_at: null,
            processed_at: null,
            last_error: null,
            invoice_provider: null,
            external_invoice_id: null,
            invoice_status: null,
            created_at: "2026-07-18T10:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/commercial/billing-disputes" && request.method() === "GET") {
      return route.fulfill({ json: disputeCreated ? [dispute] : [] });
    }
    if (path.startsWith("/api/v1/commercial/billing-disputes") && request.method() === "POST") {
      posts.push({ path, body: request.postDataJSON() as Record<string, unknown> });
      disputeCreated = true;
      return route.fulfill({
        json: path.endsWith("/transition") ? { ...dispute, status: "investigating", version: 2 } : dispute,
      });
    }
    if (path.startsWith("/api/v1/commercial/")) return route.fulfill({ json: [] });
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await page.goto("/workspace/internal?view=commercial");
  await expect(page.getByRole("heading", { name: "Agent 商业运营" })).toBeVisible();
  await page.getByRole("tab", { name: "账单投递" }).click();
  await page.getByRole("button", { name: `对账期单 ${dispute.statement_key} 发起计费争议` }).click();
  await page.getByLabel("争议额度").fill("2.5");
  await page.getByLabel("争议主题").fill(dispute.subject);
  await page.getByLabel("争议说明").fill(dispute.description);
  await page.getByRole("button", { name: "提交争议" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("tab", { name: "计费争议" }).click();
  await expect(page.getByText(dispute.subject, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: `处理计费争议 ${dispute.dispute_key}` }).click();
  await page.getByLabel("争议处理记录").fill("Finance accepted the browser dispute for investigation.");
  await page.getByRole("button", { name: "提交处理" }).click();
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[0]?.body).toMatchObject({ statement_id: dispute.statement_id, disputed_units: "2.5" });
  expect(posts[1]?.body).toMatchObject({ expected_version: 1, action: "investigate" });
}
