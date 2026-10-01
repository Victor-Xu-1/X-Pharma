import { useEffect, useRef } from "react";

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "summary",
  "[contenteditable='true']",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const modalStack: HTMLElement[] = [];

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) =>
      element.tabIndex >= 0 && element.getAttribute("aria-hidden") !== "true" && !element.closest("[hidden], [inert]"),
  );
}

function removeFromStack(container: HTMLElement) {
  const index = modalStack.lastIndexOf(container);
  if (index >= 0) modalStack.splice(index, 1);
}

export function useModalFocus<T extends HTMLElement>(
  active: boolean,
  onClose: () => void,
  { closeOnEscape = true, restoreFocus = true }: { closeOnEscape?: boolean; restoreFocus?: boolean } = {},
) {
  const containerRef = useRef<T>(null);
  const onCloseRef = useRef(onClose);
  const closeOnEscapeRef = useRef(closeOnEscape);
  const restoreFocusRef = useRef(restoreFocus);
  onCloseRef.current = onClose;
  closeOnEscapeRef.current = closeOnEscape;
  restoreFocusRef.current = restoreFocus;

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modalStack.push(container);

    const focusFrame = window.requestAnimationFrame(() => {
      // A user can choose a destination before this deferred frame runs. Do not
      // replace that focus or take it away from a newer, nested modal.
      if (!container.isConnected || modalStack.at(-1) !== container || container.contains(document.activeElement)) {
        return;
      }
      const requested = container.querySelector<HTMLElement>("[data-modal-autofocus='true']");
      const initialFocus =
        requested && focusableElements(container).includes(requested)
          ? requested
          : (focusableElements(container)[0] ?? container);
      initialFocus.focus();
    });

    const handleKeyDown = (event: KeyboardEvent) => {
      if (modalStack.at(-1) !== container) return;
      if (event.key === "Escape" && closeOnEscapeRef.current) {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = focusableElements(container);
      if (!focusable.length) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable.at(-1);
      const current = document.activeElement;
      if (event.shiftKey && (current === first || !container.contains(current))) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && (current === last || !container.contains(current))) {
        event.preventDefault();
        first?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown, true);
      removeFromStack(container);
      if (!restoreFocusRef.current) return;
      window.requestAnimationFrame(() => {
        if (previousFocus?.isConnected && !(previousFocus as HTMLButtonElement).disabled) previousFocus.focus();
      });
    };
  }, [active]);

  return containerRef;
}
