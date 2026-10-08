import { ChevronDown, X } from "lucide-react";
import { useMessages } from "../lib/i18n";
import { facetMessages } from "../lib/i18n/facets";
import { useDismissibleDetails } from "../lib/useDismissibleDetails";

export interface FacetMultiSelectOption {
  value: string;
  label: string;
  count: number;
}

export function FacetMultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: readonly FacetMultiSelectOption[];
  selected: readonly string[];
  onChange: (values: string[]) => void;
}) {
  const t = useMessages(facetMessages);
  const popover = useDismissibleDetails();
  const selectedSet = new Set(selected);
  const selectedLabels = options.filter((option) => selectedSet.has(option.value)).map((option) => option.label);
  const summary = selectedLabels.length
    ? selectedLabels.length <= 2
      ? selectedLabels.join(t("、"))
      : t("{names}等 {count} 项", { names: selectedLabels.slice(0, 2).join(t("、")), count: selectedLabels.length })
    : t("全部");

  function toggle(value: string) {
    const next = selectedSet.has(value) ? selected.filter((item) => item !== value) : [...selected, value];
    onChange(next);
  }

  return (
    <fieldset className="facet-multi-select">
      <legend>{label}</legend>
      <details {...popover}>
        <summary aria-label={t("{label}：{summary}", { label, summary })}>
          <span>{summary}</span>
          <ChevronDown size={15} aria-hidden="true" />
        </summary>
        <div className="facet-multi-select-options">
          <div className="facet-multi-select-toolbar">
            <span>{selected.length ? t("已选 {count} 项", { count: selected.length }) : t("不限制")}</span>
            <button
              type="button"
              onClick={() => onChange([])}
              disabled={!selected.length}
              aria-label={t("清除{label}选择", { label })}
              title={t("清除{label}选择", { label })}
            >
              <X size={13} aria-hidden="true" />
              {t("清除")}
            </button>
          </div>
          <div className="facet-multi-select-list">
            {options.map((option) => (
              <label key={option.value}>
                <input type="checkbox" checked={selectedSet.has(option.value)} onChange={() => toggle(option.value)} />
                <span>{option.label}</span>
                <small>{option.count}</small>
              </label>
            ))}
          </div>
        </div>
      </details>
    </fieldset>
  );
}
