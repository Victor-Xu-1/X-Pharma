import { pipelineText as t } from "../../lib/i18n/pipeline";

/** Stateless date controls; the root retains the one applied-query/draft authority. */
export function PipelineDateRange({
  label,
  from,
  to,
  onFromChange,
  onToChange,
}: {
  label: string;
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
}) {
  return (
    <fieldset className="date-range-fieldset">
      <legend>{label}</legend>
      <label>
        <span>{t("起")}</span>
        <input type="date" value={from} max={to || undefined} onChange={(event) => onFromChange(event.target.value)} />
      </label>
      <label>
        <span>{t("止")}</span>
        <input type="date" value={to} min={from || undefined} onChange={(event) => onToChange(event.target.value)} />
      </label>
    </fieldset>
  );
}
