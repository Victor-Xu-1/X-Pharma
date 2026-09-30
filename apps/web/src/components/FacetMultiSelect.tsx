import { ChevronDown, X } from "lucide-react";

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
  const selectedSet = new Set(selected);
  const selectedLabels = options.filter((option) => selectedSet.has(option.value)).map((option) => option.label);
  const summary = selectedLabels.length
    ? selectedLabels.length <= 2
      ? selectedLabels.join("、")
      : `${selectedLabels.slice(0, 2).join("、")}等 ${selectedLabels.length} 项`
    : "全部";

  function toggle(value: string) {
    const next = selectedSet.has(value) ? selected.filter((item) => item !== value) : [...selected, value];
    onChange(next);
  }

  return (
    <fieldset className="facet-multi-select">
      <legend>{label}</legend>
      <details>
        <summary aria-label={`${label}：${summary}`}>
          <span>{summary}</span>
          <ChevronDown size={15} aria-hidden="true" />
        </summary>
        <div className="facet-multi-select-options">
          <div className="facet-multi-select-toolbar">
            <span>{selected.length ? `已选 ${selected.length} 项` : "不限制"}</span>
            <button
              type="button"
              onClick={() => onChange([])}
              disabled={!selected.length}
              aria-label={`清除${label}选择`}
              title={`清除${label}选择`}
            >
              <X size={13} aria-hidden="true" />
              清除
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
