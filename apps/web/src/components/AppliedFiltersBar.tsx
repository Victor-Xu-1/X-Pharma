import { Filter, X } from "lucide-react";

import type { AppliedFilterRead } from "../lib/generated";

const operatorLabels: Record<AppliedFilterRead["operator"], string> = {
  contains: "",
  eq: "",
  in: "",
  gte: "起",
  lte: "止",
};

function displayValue(value: AppliedFilterRead["value"], labels: Readonly<Record<string, string>> | undefined): string {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.map((item) => labels?.[item] ?? item).join("、");
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) return value.slice(0, 10);
  return labels?.[String(value)] ?? String(value);
}

export function AppliedFiltersBar({
  filters,
  labels,
  valueLabels,
  onClear,
}: {
  filters: AppliedFilterRead[] | undefined;
  labels: Readonly<Record<string, string>>;
  valueLabels?: Readonly<Record<string, Readonly<Record<string, string>>>>;
  onClear?: () => void;
}) {
  if (!filters?.length) return null;

  return (
    <section className="applied-filters-bar" aria-label="已应用查询条件">
      <span className="applied-filters-title">
        <Filter size={14} />
        已应用条件
      </span>
      <div className="applied-filter-list">
        {filters.map((filter) => (
          <span className="applied-filter-chip" key={`${filter.field}-${filter.operator}-${String(filter.value)}`}>
            <strong>{labels[filter.field] ?? filter.field}</strong>
            {operatorLabels[filter.operator] ? <small>{operatorLabels[filter.operator]}</small> : null}
            <span>{displayValue(filter.value, valueLabels?.[filter.field])}</span>
          </span>
        ))}
      </div>
      {onClear ? (
        <button type="button" onClick={onClear} aria-label="清除全部已应用条件" title="清除全部条件">
          <X size={14} />
        </button>
      ) : null}
    </section>
  );
}
