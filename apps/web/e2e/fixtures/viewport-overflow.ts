import type { Page } from "@playwright/test";

/** Geometry-only diagnostics: no user values, source records or credential fields. */
export async function readViewportOverflow(page: Page) {
  return page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    elements: [...document.querySelectorAll(".workspace-main *")]
      .flatMap((node) => {
        const rect = node.getBoundingClientRect(),
          style = getComputedStyle(node);
        return rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1)
          ? [
              {
                tag: node.tagName,
                classes: node.className,
                width: rect.width,
                left: rect.left,
                right: rect.right,
                display: style.display,
                minWidth: style.minWidth,
                grid: style.gridTemplateColumns,
              },
            ]
          : [];
      })
      .slice(0, 30),
  }));
}
