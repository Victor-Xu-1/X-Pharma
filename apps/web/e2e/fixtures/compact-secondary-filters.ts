import { expect, type Page } from "@playwright/test";

/** Owned disclosure geometry only; scientific fields, counters and request behavior are unchanged. */
export async function expectCompactSecondaryFilters(page: Page) {
  if ((page.viewportSize()?.width ?? 0) > 560) return;
  const panels = page.locator(".secondary-filter-panel");
  for (const panel of await panels.all()) {
    const summary = panel.locator(":scope > summary");
    if (!(await summary.isVisible())) continue;
    const hint = summary.locator("small");
    const activeCount = await panel.getAttribute("data-active-count");
    expect(activeCount).toMatch(/^\d+$/);
    if (activeCount === "0") await expect(hint).toBeHidden();
    else await expect(hint).toBeVisible();
    const geometry = await summary.evaluate((node) => {
      const label = node.querySelector("span");
      if (!label) throw new Error("A complete filter title is required");
      const text = document.createRange();
      text.selectNodeContents(label);
      return {
        lines: new Set([...text.getClientRects()].map((rect) => Math.round(rect.top / 2) * 2)).size,
        icons: [...node.querySelectorAll("svg")].map((icon) => icon.getBoundingClientRect().width),
      };
    });
    expect(geometry.lines).toBeLessThanOrEqual(3);
    expect(geometry.icons).toHaveLength(2);
    expect(geometry.icons.every((width) => width >= 15)).toBe(true);
  }
}
