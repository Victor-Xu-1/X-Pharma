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
    let pointerActive = false;
    let releaseTimer: number | undefined;
    function releasePointer() {
      window.clearTimeout(releaseTimer);
      releaseTimer = undefined;
      pointerActive = false;
    }
    function beginPointer() {
      window.clearTimeout(releaseTimer);
      pointerActive = true;
    }
    const finishPointer = () => {
      window.clearTimeout(releaseTimer);
      // Click follows pointer-up. Defer the fallback for canceled/non-clicking
      // gestures until the intended target has completed its activation.
      releaseTimer = window.setTimeout(() => {
        releasePointer();
        if (details.open && !details.contains(document.activeElement)) details.open = false;
      }, 0);
    };
    function dismissOnClick(event: Event) {
      const userActivation = pointerActive || event.isTrusted || (event instanceof MouseEvent && event.detail > 0);
      releasePointer();
      // A managed blob download also dispatches an untrusted click from outside
      // the form. It must not hide the completed operation's feedback.
      if (userActivation) dismissOutside(event);
    }
    function dismissOnFocus(event: Event) {
      if (!pointerActive) dismissOutside(event);
    }
    // Closing an in-flow disclosure on pointer-down/focus can move the next
    // summary before pointer-up and swallow its click. Keep geometry stable for
    // that gesture; keyboard focus departure still dismisses immediately.
    document.addEventListener("pointerdown", beginPointer, true);
    document.addEventListener("pointerup", finishPointer, true);
    document.addEventListener("pointercancel", finishPointer, true);
    document.addEventListener("click", dismissOnClick);
    document.addEventListener("contextmenu", dismissOnClick);
    document.addEventListener("keydown", releasePointer, true);
    document.addEventListener("focusin", dismissOnFocus);
    return () => {
      releasePointer();
      document.removeEventListener("pointerdown", beginPointer, true);
      document.removeEventListener("pointerup", finishPointer, true);
      document.removeEventListener("pointercancel", finishPointer, true);
      document.removeEventListener("click", dismissOnClick);
      document.removeEventListener("contextmenu", dismissOnClick);
      document.removeEventListener("keydown", releasePointer, true);
      document.removeEventListener("focusin", dismissOnFocus);
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
