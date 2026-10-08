import { Filter, X } from "lucide-react";
import type { AppliedFilterRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";

const operatorLabels: Record<AppliedFilterRead["operator"], "" | "起" | "止"> = {
  contains: "",
  eq: "",
  in: "",
  gte: "起",
  lte: "止",
};

function displayValue(value: AppliedFilterRead["value"], labels: Readonly<Record<string, string>> | undefined): string {
  if (typeof value === "boolean") return value ? t("是") : t("否");
  if (Array.isArray(value)) return value.map((item) => labels?.[item] ?? item).join(t("、"));
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)) return value.slice(0, 10);
  return labels?.[String(value)] ?? String(value);
}

function operatorLabel(operator: AppliedFilterRead["operator"]): string {
  const key = operatorLabels[operator];
  return key ? t(key) : "";
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
  useLocale();
  if (!filters?.length) return null;

  return (
    <section className="applied-filters-bar" aria-label={t("已应用查询条件")}>
      <span className="applied-filters-title">
        <Filter size={14} />
        {t("已应用条件")}
      </span>
      <div className="applied-filter-list">
        {filters.map((filter) => (
          <span className="applied-filter-chip" key={`${filter.field}-${filter.operator}-${String(filter.value)}`}>
            <strong>{labels[filter.field] ?? filter.field}</strong>
            {operatorLabels[filter.operator] ? <small>{operatorLabel(filter.operator)}</small> : null}
            <span>{displayValue(filter.value, valueLabels?.[filter.field])}</span>
          </span>
        ))}
      </div>
      {onClear ? (
        <button type="button" onClick={onClear} aria-label={t("清除全部已应用条件")} title={t("清除全部条件")}>
          <X size={14} />
        </button>
      ) : null}
    </section>
  );
}
