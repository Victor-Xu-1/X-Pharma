import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { isUnavailableFacetOption, pipelineFacetCountSuffix, pipelineSelectOptions } from "./presentation";

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
  const text = useMessages(targetPipelineMessages);
  const options = pipelineSelectOptions(value, values);
  return (
    <label>
      {label}
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="">{text("全部")}</option>
        {options.map(([item, count]) => (
          <option value={item} key={item} disabled={isUnavailableFacetOption(count, item, value)}>
            {formatItem(item)}
            {pipelineFacetCountSuffix(count)}
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
  const text = useMessages(targetPipelineMessages);
  return (
    <fieldset className="date-range-fieldset">
      <legend>{legend}</legend>
      <label>
        <span>{text("起")}</span>
        <input
          type="date"
          aria-label={text("{legend}起", { legend })}
          value={from}
          max={to || undefined}
          onChange={(event) => onFromChange(event.target.value)}
        />
      </label>
      <label>
        <span>{text("止")}</span>
        <input
          type="date"
          aria-label={text("{legend}止", { legend })}
          value={to}
          min={from || undefined}
          onChange={(event) => onToChange(event.target.value)}
        />
      </label>
    </fieldset>
  );
}
