import { expect, type Page } from "@playwright/test";

/** Read-only geometry; does not modify viewport, data, source records or preference state. */
export async function expectCompactWorkspaceHeading(page: Page) {
  if ((page.viewportSize()?.width ?? 0) > 760) return;
  const heading = page.locator(".page-heading");
  await expect(page.locator(".topbar .language-switcher select")).toBeVisible();
  await expect(heading.locator(".language-switcher")).toHaveCount(0);
  const geometry = await heading.evaluate((node) => ({
    available: node.getBoundingClientRect().width,
    title: node.querySelector("h1")?.getBoundingClientRect().width ?? 0,
  }));
  expect(geometry.title).toBeGreaterThanOrEqual(geometry.available - 1);
}

export async function expectCompactTableToolbar(page: Page, selected: boolean) {
  if ((page.viewportSize()?.width ?? 0) > 560) return;
  const toolbar = page.locator(".virtual-table-toolbar").first();
  await expect(toolbar.locator(".table-density-control button").first()).toBeEnabled();
  const geometry = await toolbar.evaluate((node) => {
    const rect = node.getBoundingClientRect();
    const children = [...node.children]
      .map((child) => child.getBoundingClientRect())
      .filter((child) => child.height > 0);
    const tops = children.map((child) => child.top).sort((left, right) => left - right);
    const rows = tops.filter((top, index) => index === 0 || top - tops[index - 1] > 8).length;
    return {
      rows,
      clipped: children.filter((child) => child.left < rect.left - 1 || child.right > rect.right + 1).length,
    };
  });
  expect(geometry.rows).toBeLessThanOrEqual(selected ? 4 : 3);
  expect(geometry.clipped).toBe(0);
  if (selected) await expect(toolbar.locator(".table-selection-status")).toBeVisible();
  else await expect(toolbar.locator(".table-selection-status")).toBeHidden();
  await expect(toolbar.locator(".table-density-control button")).toHaveCount(2);
  await expect(toolbar.locator(".table-column-menu summary")).toBeVisible();
  await expect(toolbar.locator(".table-view-reset")).toBeVisible();
}
