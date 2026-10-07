import { type RefObject, useEffect } from "react";

/** Scoped to the mounted search input, never steals typing or a modal's keyboard focus. */
export function useSearchShortcut(input: RefObject<HTMLInputElement | null>) {
  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      if (
        event.key !== "/" ||
        event.defaultPrevented ||
        event.isComposing ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey
      )
        return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.closest(
          "input, textarea, select, [contenteditable]:not([contenteditable='false']), [role='textbox'], [role='combobox']",
        )
      )
        return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      const field = input.current;
      if (!field || field.disabled) return;
      event.preventDefault();
      field.focus();
    }
    document.addEventListener("keydown", focusSearch);
    return () => document.removeEventListener("keydown", focusSearch);
  }, [input]);
}
