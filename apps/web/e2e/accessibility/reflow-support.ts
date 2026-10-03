import { expect, type Page } from "@playwright/test";

export async function expectPageReflow(page: Page, context: string) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(
    dimensions.scrollWidth,
    `${context} creates page-level horizontal overflow at ${dimensions.clientWidth} CSS px`,
  ).toBeLessThanOrEqual(dimensions.clientWidth);
}

export async function expectNamedKeyboardScrollableTables(page: Page, context: string) {
  const invalidRegions = await page.locator(".table-frame").evaluateAll((regions) =>
    regions.flatMap((region, index) => {
      const label = region.getAttribute("aria-label")?.trim() ?? "";
      const role = region.getAttribute("role");
      const tabIndex = (region as HTMLElement).tabIndex;
      const hasRegionSemantics = region.tagName === "SECTION" || role === "region";
      return hasRegionSemantics && label && tabIndex === 0 ? [] : [{ index, label, role, tabIndex }];
    }),
  );
  expect(invalidRegions, `${context} has unnamed or keyboard-inaccessible horizontal table regions`).toEqual([]);
}
