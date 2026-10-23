import { type RefObject, useLayoutEffect } from "react";

export function revealHorizontalItem(rail: HTMLElement, button: HTMLElement) {
  if (!rail.contains(button)) return;
  const visible = rail.getBoundingClientRect();
  const selected = button.getBoundingClientRect();
  if (selected.left < visible.left || selected.width > visible.width) {
    rail.scrollLeft += selected.left - visible.left;
  } else if (selected.right > visible.right) {
    rail.scrollLeft += selected.right - visible.right;
  }
}

/** Reveal selection on its own horizontal rail without moving page scroll or focus. */
export function useHorizontalActiveItem(
  railRef: RefObject<HTMLElement | null>,
  selectedRef: RefObject<HTMLElement | null>,
  items: ReadonlyArray<{ key: string }>,
  activeKey: string,
) {
  useLayoutEffect(() => {
    if (!items.some((item) => item.key === activeKey)) return;
    const rail = railRef.current;
    const button = selectedRef.current;
    if (!rail || !button || !rail.contains(button)) return;
    function alignHorizontally() {
      if (!rail || !button) return;
      revealHorizontalItem(rail, button);
    }
    alignHorizontally();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(alignHorizontally);
    observer.observe(rail);
    observer.observe(button);
    return () => observer.disconnect();
  }, [activeKey, items, railRef, selectedRef]);
}
