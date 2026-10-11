import { expect, type Page } from "@playwright/test";

/** Explicitly open the form; this must never submit a public-source query. */
export async function expectPublicResearchFormLayout(page: Page) {
  const panel = page.getByTestId("public-research-panel");
  if ((await panel.getAttribute("open")) === null) await panel.locator(":scope > summary").click();
  const form = panel.getByRole("form");
  await expect(form).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const metrics = await form.locator("input, select, button").evaluateAll((nodes) =>
    nodes.map((node) => {
      const bounds = node.getBoundingClientRect();
      const row = node.parentElement;
      if (!row) throw new Error("Research controls must retain their own form row");
      const style = getComputedStyle(row);
      const range = document.createRange();
      range.selectNodeContents(node);
      return {
        tag: node.tagName,
        height: bounds.height,
        width: bounds.width,
        available:
          row.getBoundingClientRect().width -
          Number.parseFloat(style.paddingLeft) -
          Number.parseFloat(style.paddingRight),
        lines: new Set(
          Array.from(range.getClientRects())
            .filter((line) => line.width > 0)
            .map((line) => line.top.toFixed(1)),
        ).size,
      };
    }),
  );
  console.log(JSON.stringify({ scope: "public research form layout only", metrics }));
  expect(metrics).toHaveLength(3);
  for (const control of metrics) {
    expect(control.height, "Research controls keep the original single-line touch height").toBeGreaterThanOrEqual(38);
    expect(control.height, "Neighbouring buttons must not stretch inputs or selects").toBeLessThanOrEqual(50);
    if ((page.viewportSize()?.width ?? 0) <= 560) {
      expect(control.width, "Narrow research controls use their complete row").toBeGreaterThanOrEqual(
        control.available - 1,
      );
    }
    if (control.tag === "BUTTON") expect(control.lines, "The research action retains one readable line").toBe(1);
  }
}
