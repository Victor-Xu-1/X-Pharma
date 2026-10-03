import type { PlaywrightTestArgs, PlaywrightWorkerArgs } from "@playwright/test";
import { expect } from "@playwright/test";

export async function verifyKnowledgeGovernance({ page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "knowledge-user",
          tenant_id: "knowledge-tenant",
          email: "knowledge@example.test",
          display_name: "Knowledge Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/knowledge/pages") {
      return route.fulfill({
        json: [
          {
            current_version_id: "knowledge-version-2",
            id: "knowledge-page-1",
            page_key: "entity/target/egfr",
            page_type: "target",
            status: "published",
            subject_entity_id: "target-egfr",
            title: "EGFR competitive landscape",
            updated_at: "2026-07-24T08:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1") {
      return route.fulfill({
        json: {
          current_version_id: "knowledge-version-2",
          id: "knowledge-page-1",
          page_key: "entity/target/egfr",
          page_type: "target",
          status: "published",
          subject_entity_id: "target-egfr",
          title: "EGFR competitive landscape",
          updated_at: "2026-07-24T08:00:00Z",
          compiler_version: "knowledge-v1",
          content_json: {},
          content_sha256: "a".repeat(64),
          rendered_markdown: "# EGFR\n\nGoverned competitive landscape with source citations.",
          source_snapshot_at: "2026-07-24T08:00:00Z",
          version_number: 2,
        },
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1/coverage") {
      return route.fulfill({
        json: {
          cited_fact_count: 3,
          fact_count: 3,
          linked_entity_count: 2,
          page_id: "knowledge-page-1",
          predicates: [
            { cited_fact_count: 2, fact_count: 2, predicate: "has_competitor" },
            { cited_fact_count: 1, fact_count: 1, predicate: "has_target_class" },
          ],
          source_count: 2,
          source_snapshot_at: "2026-07-24T08:00:00Z",
          uncited_fact_count: 0,
          version_id: "knowledge-version-2",
          version_number: 2,
        },
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1/versions") {
      return route.fulfill({
        json: [
          {
            added_fact_count: 1,
            added_source_count: 1,
            compiler_version: "knowledge-v1",
            content_sha256: "a".repeat(64),
            created_at: "2026-07-24T08:00:00Z",
            created_by_run_id: "governance-run-2",
            fact_count: 3,
            is_current: true,
            previous_version_number: 1,
            removed_fact_count: 0,
            removed_source_count: 0,
            source_count: 2,
            source_snapshot_at: "2026-07-24T08:00:00Z",
            version_id: "knowledge-version-2",
            version_number: 2,
          },
          {
            added_fact_count: 2,
            added_source_count: 1,
            compiler_version: "knowledge-v1",
            content_sha256: "b".repeat(64),
            created_at: "2026-07-23T08:00:00Z",
            created_by_run_id: "governance-run-1",
            fact_count: 2,
            is_current: false,
            previous_version_number: null,
            removed_fact_count: 0,
            removed_source_count: 0,
            source_count: 1,
            source_snapshot_at: "2026-07-23T08:00:00Z",
            version_id: "knowledge-version-1",
            version_number: 1,
          },
        ],
      });
    }
    if (path.endsWith("/diff")) {
      const versionNumber = path.includes("/versions/1/") ? 1 : 2;
      return route.fulfill({
        json: {
          added_fact_count: versionNumber === 2 ? 1 : 2,
          added_facts: [
            {
              change_key: `knowledge-change-${versionNumber}`,
              citation_number: 2,
              confidence: 0.95,
              fact_id: "fact-competitor",
              object_entity_name: "Drug B",
              predicate: "has_competitor",
              source_document_id: "source-competitive-update",
              source_locator: "page=8",
              source_title: "Competitive landscape update",
              value: { name: "Drug B" },
            },
          ],
          added_source_count: 1,
          added_sources: [
            {
              locator: "page=8",
              source_document_id: "source-competitive-update",
              source_uri: "file:///research/competitive-update.pdf",
              title: "Competitive landscape update",
            },
          ],
          from_version_number: versionNumber === 2 ? 1 : null,
          page_id: "knowledge-page-1",
          removed_fact_count: 0,
          removed_facts: [],
          removed_source_count: 0,
          removed_sources: [],
          to_version_number: versionNumber,
          truncated: false,
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=knowledge");
  await expect(page.getByRole("heading", { name: "版本化知识专题" })).toBeVisible();
  await page.getByRole("button", { name: /EGFR competitive landscape/ }).click();
  await expect(page.getByRole("heading", { name: "EGFR competitive landscape" })).toBeVisible();
  await page.getByRole("tab", { name: "覆盖与版本" }).click();
  await expect(page.getByRole("region", { name: "专题覆盖摘要" })).toContainText("3专题要点");
  await expect(page.getByRole("cell", { name: "has_competitor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "v1 → v2" })).toBeVisible();
  await expect(page.getByText("Competitive landscape update", { exact: true })).toBeVisible();
  await expect(page.getByText("page=8", { exact: true })).toBeVisible();
  await page.getByRole("list", { name: "专题版本" }).getByRole("button", { name: /v1/ }).click();
  await expect(page.getByRole("heading", { name: "初始版本 v1" })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
}
