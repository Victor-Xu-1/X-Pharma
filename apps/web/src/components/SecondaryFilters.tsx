import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";

type SecondaryFiltersProps = {
  activeCount: number;
  children: ReactNode;
  label?: string;
  className?: string;
  contentClassName?: string;
};

/** One disclosure lifecycle, reusable above a temporarily unmounted query renderer. */
export function useSecondaryFiltersState(activeCount: number) {
  const [open, setOpen] = useState(activeCount > 0);
  useEffect(() => {
    if (activeCount > 0) setOpen(true);
  }, [activeCount]);
  return { open, setOpen };
}

/** Default consumers own one local disclosure; never a query, route or permission. */
export function SecondaryFilters(props: SecondaryFiltersProps) {
  const state = useSecondaryFiltersState(props.activeCount);
  return <SecondaryFiltersPanel {...props} state={state} />;
}

/** One presentation renderer; hoisted consumers supply the same lifecycle state. */
export function SecondaryFiltersPanel({
  activeCount,
  children,
  label = t("更多筛选"),
  className,
  contentClassName = "secondary-filter-grid",
  state,
}: SecondaryFiltersProps & { state: ReturnType<typeof useSecondaryFiltersState> }) {
  useLocale();
  const { open, setOpen } = state;
  return (
    <details
      className={`advanced-filter-panel secondary-filter-panel${className ? ` ${className}` : ""}`}
      data-active-count={activeCount}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <SlidersHorizontal size={15} aria-hidden="true" />
        <span>{label}</span>
        <small>{activeCount > 0 ? t("已选 {count} 项", { count: activeCount }) : t("按需展开")}</small>
        <ChevronDown className="disclosure-chevron" size={16} aria-hidden="true" />
      </summary>
      <div className={contentClassName}>{children}</div>
    </details>
  );
}
