import { expect, type Locator, type Page } from "@playwright/test";

/** Layout evidence only; horizontal data scrolling and original fields remain intact. */
export async function expectResearchReadingLayout(page: Page, table: Locator) {
  await page.evaluate(() => document.fonts.ready);
  const title = await page
    .getByTestId("public-research-panel")
    .locator(":scope > summary")
    .evaluate((summary) => {
      const node =
        summary.querySelector("strong") ??
        Array.from(summary.childNodes).find((child) => child.nodeType === Node.TEXT_NODE && child.textContent?.trim());
      if (!node) throw new Error("The public-source title must remain present");
      const range = document.createRange();
      range.selectNodeContents(node);
      return new Set(
        Array.from(range.getClientRects())
          .filter((line) => line.width > 0)
          .map((line) => line.top.toFixed(1)),
      ).size;
    });
  const controls = await page
    .locator('.secondary-filter-grid input:not([type="checkbox"]), .secondary-filter-grid select')
    .evaluateAll((nodes) => nodes.map((node) => node.getBoundingClientRect().height));
  const clippedHeadings = await table.locator("thead .virtual-table-heading button > span").evaluateAll((nodes) =>
    nodes.flatMap((node) => {
      const bounds = node.getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(node);
      return Array.from(range.getClientRects()).some(
        (line) => line.left < bounds.left - 1 || line.right > bounds.right + 1,
      )
        ? [node.textContent]
        : [];
    }),
  );
  console.log(
    JSON.stringify({ scope: "controlled research reading layout", titleLines: title, controls, clippedHeadings }),
  );
  expect(title, "The public-source title has its own readable line").toBe(1);
  expect(controls.length, "Expanded advanced fields stay present").toBeGreaterThan(0);
  for (const height of controls) {
    expect(height, "Date groups must not stretch adjacent single-line fields").toBeLessThanOrEqual(50);
    expect(height, "Controls retain their original touchable height").toBeGreaterThanOrEqual(38);
  }
  expect(clippedHeadings, "Sortable column labels must remain fully readable inside their own columns").toEqual([]);
}
