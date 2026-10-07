import { type KeyboardEvent, useEffect, useState } from "react";

/** Dismiss transient native popovers without duplicating their open/draft state. */
export function useDismissibleDetails({ dismissible = true }: { dismissible?: boolean } = {}) {
  const [details, setDetails] = useState<HTMLDetailsElement | null>(null);

  useEffect(() => {
    if (!details) return;
    if (!dismissible) {
      const guardTrigger = (event: MouseEvent) => {
        const summary = details.querySelector(":scope > summary");
        if (details.open && event.target instanceof Node && summary?.contains(event.target)) {
          event.preventDefault();
        }
      };
      // Native summary has no disabled attribute. Keep pending feedback visible
      // without replacing its native disclosure semantics with another control.
      details.addEventListener("click", guardTrigger);
      return () => details.removeEventListener("click", guardTrigger);
    }
    const dismissOutside = (event: Event) => {
      if (details.open && event.target instanceof Node && !details.contains(event.target)) {
        details.open = false;
      }
    };
    // Check native open synchronously: toggle is deferred and can otherwise
    // miss a quick outside gesture. Closing never resets selections or drafts.
    document.addEventListener("pointerdown", dismissOutside, true);
    document.addEventListener("focusin", dismissOutside);
    return () => {
      document.removeEventListener("pointerdown", dismissOutside, true);
      document.removeEventListener("focusin", dismissOutside);
    };
  }, [details, dismissible]);

  function onKeyDown(event: KeyboardEvent<HTMLDetailsElement>) {
    if (
      !dismissible ||
      !event.currentTarget.open ||
      event.key !== "Escape" ||
      event.defaultPrevented ||
      event.nativeEvent.isComposing ||
      event.repeat
    ) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.open = false;
    event.currentTarget.querySelector<HTMLElement>(":scope > summary")?.focus();
  }

  return { ref: setDetails, onKeyDown };
}
