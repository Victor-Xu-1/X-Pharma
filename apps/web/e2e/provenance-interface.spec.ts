import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { verifyEpidemiologyPatientPopulation } from "./workspace/epidemiology-patient-population";

test("[provenance-language] preserves quotes, full credit and cached evidence across cross-tab language switching", async ({
  page,
  context,
}) => {
  // Reuse the existing browser-only governed observation and identity fixture.
  // No original scientific/profile records or external provider requests are written.
  await verifyEpidemiologyPatientPopulation({ page });
  let reads = 0;
  const credit = "Tenant-provided source material; required credit: 原始作者 Research Institute";
  await page.route("**/api/v1/provenance/**", (route) => {
    reads += 1;
    return route.fulfill({
      json: {
        resource_type: "epidemiology_observation",
        resource_id: "550e8400-e29b-41d4-a716-446655440010",
        license_scopes: [],
        warnings: [],
        items: [
          {
            id: "controlled-evidence-1",
            resource_type: "epidemiology_observation",
            resource_id: "550e8400-e29b-41d4-a716-446655440010",
            dataset_key: "hidden-fixture-key",
            document_name: "Controlled evidence / 来源原文",
            quote: "原始证据 EGFR — browser fixture, not a real study",
            locator: "page=7;paragraph=2",
            created_at: "2026-10-08T00:00:00Z",
            review_status: "verified",
            license: { attribution: credit },
            warnings: [],
            source_uri: "https://example.test/controlled-source",
          },
        ],
      },
    });
  });
  await page
    .getByRole("button", { name: /^查看 .* 的原始证据$/ })
    .first()
    .click();
  const drawer = page.getByRole("dialog", { name: "原始证据", exact: true });
  await expect(drawer).toContainText(credit);
  await expect(drawer).toContainText("page=7;paragraph=2");
  await expect(drawer).not.toContainText("hidden-fixture-key");
  expect(reads).toBe(1);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  const languagePage = await context.newPage();
  await languagePage.goto("/workspace/research");
  await languagePage.getByRole("combobox", { name: /^(界面语言|Interface language)$/ }).selectOption("en");
  const english = page.getByRole("dialog", { name: "Original evidence", exact: true });
  await expect(english).toContainText("Original text excerpt provided");
  await expect(english).toContainText("原始证据 EGFR — browser fixture, not a real study");
  await expect(english).toContainText(credit);
  expect(reads).toBe(1);
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  await languagePage.close();
  await page.getByRole("button", { name: "Close original evidence", exact: true }).click();
  await expect(english).toHaveCount(0);
});
