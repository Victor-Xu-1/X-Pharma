import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyResearchPublicationTimeline({
  page,
}: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  const requestedScopes: Array<string | null> = [];
  await page.route("**/api/v1/**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "publication-user",
          tenant_id: "publication-tenant",
          email: "publication@example.test",
          display_name: "Publication Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/news-events") {
      const contentScope = requestUrl.searchParams.get("content_scope");
      requestedScopes.push(contentScope);
      const researchMode = contentScope === "research";
      return route.fulfill({
        json: {
          items: [
            {
              id: researchMode ? "poster-1" : "announcement-1",
              event_identifier: researchMode ? "ASCO-POSTER-1" : "ANNOUNCEMENT-1",
              event_type: researchMode ? "poster" : "corporate_announcement",
              title: researchMode ? "ASCO 2026 EGFR poster" : "EGFR corporate update",
              summary: "Governed source-backed research update.",
              published_at: "2026-06-05T08:00:00Z",
              language: "en",
              publisher_entity_id: "publication-publisher",
              related_entity_ids: ["publication-target"],
              canonical_url: "https://example.test/asco/egfr-poster",
              venue: "ASCO 2026",
              details: {},
              source_document_id: "publication-source",
              publisher_entity: {
                id: "publication-publisher",
                name: "Research Publisher",
                entity_type: "organization",
              },
              related_entities: [{ id: "publication-target", name: "EGFR", entity_type: "target" }],
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
          facets: {
            event_type: researchMode ? { poster: 1 } : { corporate_announcement: 1 },
            publisher: { "Research Publisher": 1 },
            language: { en: 1 },
            venue: { "ASCO 2026": 1 },
          },
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=news");
  await expect(page.getByRole("heading", { name: "新闻、公告与会议动态" })).toBeVisible();
  await expect(page.getByRole("table", { name: "新闻与会议结果" })).toBeVisible();
  await page.getByRole("button", { name: "研究发布时间线" }).click();
  await expect(page).toHaveURL(/content_scope=research/);
  await expect(page).toHaveURL(/display=timeline/);
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ASCO 2026 EGFR poster" })).toBeVisible();
  await expect(page.getByText("会议海报", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "原始发布页" })).toHaveAttribute(
    "href",
    "https://example.test/asco/egfr-poster",
  );
  expect(requestedScopes).toContain("research");
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
