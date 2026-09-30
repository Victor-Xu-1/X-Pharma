import type { ReactNode } from "react";

export function ScrollableTableRegion({
  ariaLabel,
  children,
  className = "",
}: {
  ariaLabel: string;
  children: ReactNode;
  className?: string;
}) {
  const classes = ["table-frame", className].filter(Boolean).join(" ");
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: keyboard users need a focus target for horizontal table scrolling.
    <section className={classes} aria-label={ariaLabel} tabIndex={0}>
      {children}
    </section>
  );
}
