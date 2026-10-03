import { SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";

/** Presentation only: drafts and applied URL conditions remain owned by the domain view. */
export function SecondaryFilters({
  activeCount,
  children,
  label = "更多筛选",
}: {
  activeCount: number;
  children: ReactNode;
  label?: string;
}) {
  return (
    <details className="advanced-filter-panel secondary-filter-panel" open={activeCount > 0 || undefined}>
      <summary>
        <SlidersHorizontal size={15} aria-hidden="true" />
        <span>{label}</span>
        <small>{activeCount > 0 ? `已选 ${activeCount} 项` : "按需展开"}</small>
      </summary>
      <div className="secondary-filter-grid">{children}</div>
    </details>
  );
}
