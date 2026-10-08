import { type FocusEvent, type RefObject, useEffect, useRef } from "react";
import { useCommittedCallback } from "./useCommittedCallback";

/** Keep an in-flow surface stable through a pointer gesture; keyboard blur is immediate. */
export function useFocusDismissal({
  open,
  rootRef,
  onDismiss,
}: {
  open: boolean;
  rootRef: RefObject<HTMLElement | null>;
  onDismiss: () => void;
}) {
  const pointerActive = useRef(false);
  const dismiss = useCommittedCallback(onDismiss);
  useEffect(() => {
    if (!open) return;
    let releaseTimer: number | undefined;
    const outside = (target: EventTarget | null) => target instanceof Node && !rootRef.current?.contains(target);
    function reset() {
      window.clearTimeout(releaseTimer);
      releaseTimer = undefined;
      pointerActive.current = false;
    }
    function begin() {
      reset();
      pointerActive.current = true;
    }
    function finish() {
      // The click following pointerup must activate before collapsing the surface.
      releaseTimer = window.setTimeout(() => {
        reset();
        if (outside(document.activeElement)) dismiss();
      }, 0);
    }
    function click(event: Event) {
      reset();
      if (outside(event.target)) dismiss();
    }
    document.addEventListener("pointerdown", begin, true);
    document.addEventListener("pointerup", finish, true);
    document.addEventListener("pointercancel", finish, true);
    document.addEventListener("click", click);
    document.addEventListener("keydown", reset, true);
    return () => {
      reset();
      document.removeEventListener("pointerdown", begin, true);
      document.removeEventListener("pointerup", finish, true);
      document.removeEventListener("pointercancel", finish, true);
      document.removeEventListener("click", click);
      document.removeEventListener("keydown", reset, true);
    };
  }, [open, rootRef, dismiss]);

  return (event: FocusEvent<HTMLInputElement>) => {
    if (pointerActive.current) return;
    const target = event.relatedTarget;
    if (target instanceof HTMLButtonElement && target.type === "submit") return;
    if (target instanceof Node && rootRef.current?.contains(target)) return;
    dismiss();
  };
}
