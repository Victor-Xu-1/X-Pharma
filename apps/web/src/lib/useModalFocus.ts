import { type RefObject, useEffect, useRef } from "react";

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
const backgroundLocks = new Map<HTMLElement, { count: number; original: string | null }>();

function isolateBackground(container: HTMLElement, exceptions: ReadonlyArray<HTMLElement | null>) {
  const locked: HTMLElement[] = [];
  for (let branch: HTMLElement | null = container; branch?.parentElement; branch = branch.parentElement) {
    for (const sibling of branch.parentElement.children) {
      if (
        sibling === branch ||
        !(sibling instanceof HTMLElement) ||
        exceptions.includes(sibling) ||
        sibling.matches("script, style, link")
      )
        continue;
      const lock = backgroundLocks.get(sibling);
      if (lock) lock.count += 1;
      else {
        backgroundLocks.set(sibling, { count: 1, original: sibling.getAttribute("inert") });
        sibling.setAttribute("inert", "");
      }
      locked.push(sibling);
    }
    if (branch.parentElement === document.body) break;
  }
  return () => {
    for (const element of locked) {
      const lock = backgroundLocks.get(element);
      if (!lock || --lock.count > 0) continue;
      if (lock.original === null) element.removeAttribute("inert");
      else element.setAttribute("inert", lock.original);
      backgroundLocks.delete(element);
    }
  };
}

function isReachable(element: HTMLElement): boolean {
  if (
    !element.isConnected ||
    element.matches(":disabled") ||
    element.closest('[hidden], [inert], [aria-hidden="true"]')
  ) {
    return false;
  }
  const style = getComputedStyle(element);
  if (style.visibility === "hidden" || style.visibility === "collapse") return false;
  for (let ancestor: HTMLElement | null = element; ancestor; ancestor = ancestor.parentElement) {
    if (getComputedStyle(ancestor).display === "none") return false;
    if (ancestor instanceof HTMLDetailsElement && !ancestor.open) {
      const summary = Array.from(ancestor.children).find((child) => child.tagName === "SUMMARY");
      if (!summary?.contains(element)) return false;
    }
  }
  return true;
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) => element.tabIndex >= 0 && isReachable(element),
  );
}

function removeFromStack(container: HTMLElement) {
  const index = modalStack.lastIndexOf(container);
  if (index >= 0) modalStack.splice(index, 1);
}

export function useModalFocus<T extends HTMLElement>(
  active: boolean,
  onClose: () => void,
  {
    closeOnEscape = true,
    restoreFocus = true,
    backgroundExceptions = [],
  }: {
    closeOnEscape?: boolean;
    restoreFocus?: boolean;
    /** Exact, caller-owned pointer-dismissal controls; never an entire branch. */
    backgroundExceptions?: ReadonlyArray<RefObject<HTMLElement | null>>;
  } = {},
) {
  const containerRef = useRef<T>(null);
  const onCloseRef = useRef(onClose);
  const closeOnEscapeRef = useRef(closeOnEscape);
  const restoreFocusRef = useRef(restoreFocus);
  const backgroundExceptionsRef = useRef(backgroundExceptions);
  onCloseRef.current = onClose;
  closeOnEscapeRef.current = closeOnEscape;
  restoreFocusRef.current = restoreFocus;
  backgroundExceptionsRef.current = backgroundExceptions;

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    modalStack.push(container);
    const restoreBackground = isolateBackground(
      container,
      backgroundExceptionsRef.current.map((ref) => ref.current),
    );

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

    const handleEscape = (event: KeyboardEvent) => {
      if (modalStack.at(-1) !== container) return;
      if (
        event.key === "Escape" &&
        closeOnEscapeRef.current &&
        !event.defaultPrevented &&
        !event.isComposing &&
        !event.repeat
      ) {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
      }
    };

    const handleTab = (event: KeyboardEvent) => {
      if (modalStack.at(-1) !== container || event.key !== "Tab") return;

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

    // Trap traversal in capture, but let editors and child popovers consume
    // Escape before the topmost modal handles it in the bubble phase.
    document.addEventListener("keydown", handleTab, true);
    document.addEventListener("keydown", handleEscape);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleTab, true);
      document.removeEventListener("keydown", handleEscape);
      removeFromStack(container);
      restoreBackground();
      if (!restoreFocusRef.current) return;
      window.requestAnimationFrame(() => {
        const activeModal = modalStack.at(-1);
        if (previousFocus && isReachable(previousFocus) && (!activeModal || activeModal.contains(previousFocus))) {
          previousFocus.focus();
        }
      });
    };
  }, [active]);

  return containerRef;
}
