/** Reveal only the focused input owned by this pipeline when sticky chrome obscures it. */
export function revealFocusedPipelineControl(root: HTMLElement | null): void {
  const active = root?.ownerDocument.activeElement;
  if (
    !root ||
    !(active instanceof HTMLElement) ||
    !root.contains(active) ||
    !active.closest(".target-evidence-filters, .pipeline-advanced-filters")
  )
    return;
  const viewport = root.ownerDocument.defaultView;
  if (!viewport) return;
  const bounds = active.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const header = root.closest(".workspace-main")?.querySelector(".topbar")?.getBoundingClientRect();
  const feedback = root.querySelector(".target-pipeline-feedback")?.getBoundingClientRect();
  const headerBottom = header && header.height > 0 ? header.bottom : 0;
  const feedbackBottom =
    feedback && feedback.top < viewport.innerHeight && feedback.bottom > headerBottom ? feedback.bottom : 0;
  const visibleTop = Math.max(headerBottom, feedbackBottom) + 8;
  const visibleBottom = viewport.innerHeight - 8;
  const delta =
    bounds.top < visibleTop
      ? bounds.top - visibleTop
      : bounds.bottom > visibleBottom
        ? bounds.bottom - visibleBottom
        : 0;
  if (delta) viewport.scrollBy({ top: delta, behavior: "instant" });
}
