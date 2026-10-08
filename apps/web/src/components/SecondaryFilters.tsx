import { ChevronDown, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";

/** Presentation only: drafts and applied URL conditions remain owned by the domain view. */
export function SecondaryFilters({
  activeCount,
  children,
  label = t("更多筛选"),
}: {
  activeCount: number;
  children: ReactNode;
  label?: string;
}) {
  useLocale();
  return (
    <details className="advanced-filter-panel secondary-filter-panel" open={activeCount > 0 || undefined}>
      <summary>
        <SlidersHorizontal size={15} aria-hidden="true" />
        <span>{label}</span>
        <small>{activeCount > 0 ? t("已选 {count} 项", { count: activeCount }) : t("按需展开")}</small>
        <ChevronDown className="disclosure-chevron" size={16} aria-hidden="true" />
      </summary>
      <div className="secondary-filter-grid">{children}</div>
    </details>
  );
}
