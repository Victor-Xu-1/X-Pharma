import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";

export function DateRangeFields({
  label,
  from,
  to,
  onFrom,
  onTo,
}: {
  label: string;
  from: string;
  to: string;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
}) {
  useLocale();
  return (
    <fieldset className="compact-range-fields">
      <legend>{label}</legend>
      <label>
        <span>{t("起")}</span>
        <input type="date" value={from} onChange={(event) => onFrom(event.target.value)} />
      </label>
      <label>
        <span>{t("止")}</span>
        <input type="date" value={to} onChange={(event) => onTo(event.target.value)} />
      </label>
    </fieldset>
  );
}

export function AmountRangeFields({
  label,
  minimum,
  maximum,
  onMinimum,
  onMaximum,
}: {
  label: string;
  minimum: string;
  maximum: string;
  onMinimum: (value: string) => void;
  onMaximum: (value: string) => void;
}) {
  useLocale();
  return (
    <fieldset className="compact-range-fields">
      <legend>{label}</legend>
      <label>
        <span>{t("下限")}</span>
        <input type="number" min="0" step="any" value={minimum} onChange={(event) => onMinimum(event.target.value)} />
      </label>
      <label>
        <span>{t("上限")}</span>
        <input type="number" min="0" step="any" value={maximum} onChange={(event) => onMaximum(event.target.value)} />
      </label>
    </fieldset>
  );
}
