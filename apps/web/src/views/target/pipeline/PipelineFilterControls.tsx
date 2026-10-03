import { isUnavailableFacetOption, pipelineSelectOptions } from "./presentation";

export function TargetPipelineSelect({
  label,
  value,
  values,
  onChange,
  formatItem = (item) => item,
  disabled = false,
}: {
  label: string;
  value: string;
  values: Record<string, number> | undefined;
  onChange: (value: string) => void;
  formatItem?: (value: string) => string;
  disabled?: boolean;
}) {
  const options = pipelineSelectOptions(value, values);
  return (
    <label>
      {label}
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {options.map(([item, count]) => (
          <option value={item} key={item} disabled={isUnavailableFacetOption(count, item, value)}>
            {formatItem(item)} ({count})
          </option>
        ))}
      </select>
    </label>
  );
}
export function TargetPipelineDateRange({
  legend,
  from,
  to,
  onFromChange,
  onToChange,
}: {
  legend: string;
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
}) {
  return (
    <fieldset className="date-range-fieldset">
      <legend>{legend}</legend>
      <label>
        <span>起</span>
        <input
          type="date"
          aria-label={`${legend}起`}
          value={from}
          max={to || undefined}
          onChange={(event) => onFromChange(event.target.value)}
        />
      </label>
      <label>
        <span>止</span>
        <input
          type="date"
          aria-label={`${legend}止`}
          value={to}
          min={from || undefined}
          onChange={(event) => onToChange(event.target.value)}
        />
      </label>
    </fieldset>
  );
}
