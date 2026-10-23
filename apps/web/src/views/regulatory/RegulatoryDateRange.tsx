import { useLocale } from "../../lib/i18n";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
export function RegulatoryDateRange({
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
    <fieldset className="filter-range-field">
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
