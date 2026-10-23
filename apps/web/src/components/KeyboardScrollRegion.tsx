import type { ReactNode } from "react";

/** Shared focus target for an explicitly named, keyboard-scrollable content region. */
export function KeyboardScrollRegion({
  ariaLabel,
  children,
  className,
}: {
  ariaLabel: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: keyboard users need a focus target to scroll the named content region.
    <section className={className} aria-label={ariaLabel} tabIndex={0}>
      {children}
    </section>
  );
}
