import type { Page } from "@playwright/test";

/** Read-only evidence for the observed intermittent paint defect, never a style repair. */
export function renderedPaintEvidence(page: Page) {
  return page.evaluate(() => ({
    fonts: document.fonts.status,
    scroll: { x: scrollX, y: scrollY },
    focus: { tag: document.activeElement?.tagName, label: document.activeElement?.closest("label")?.textContent },
    elements: [
      ...document.querySelectorAll<HTMLElement>(
        ".workspace-main h2, .target-pipeline-panel input, .target-pipeline-panel select",
      ),
    ]
      .filter((node) => node.getClientRects().length > 0)
      .map((node) => {
        const rect = node.getBoundingClientRect(),
          style = getComputedStyle(node);
        return {
          tag: node.tagName,
          label: node.closest("label")?.textContent ?? node.textContent,
          bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
          style: {
            color: style.color,
            background: style.backgroundColor,
            border: style.border,
            opacity: style.opacity,
            visibility: style.visibility,
            appearance: style.appearance,
            font: style.font,
          },
        };
      }),
  }));
}
