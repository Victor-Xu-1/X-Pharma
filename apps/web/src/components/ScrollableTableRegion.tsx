import type { ReactNode } from "react";
import { KeyboardScrollRegion } from "./KeyboardScrollRegion";

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
    <KeyboardScrollRegion className={classes} ariaLabel={ariaLabel}>
      {children}
    </KeyboardScrollRegion>
  );
}
