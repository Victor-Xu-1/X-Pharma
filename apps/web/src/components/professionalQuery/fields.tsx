import { useEffect, useState } from "react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import {
  identifyProfessionalDatePreset,
  type ProfessionalDatePreset,
  resolveProfessionalDatePreset,
} from "../../lib/professionalSearch";
import { FacetMultiSelect, type FacetMultiSelectOption } from "../FacetMultiSelect";
import type { FacetCatalogState } from "./presentation";

function GovernedFacetPlaceholder({ label, state }: { label: string; state: Exclude<FacetCatalogState, "ready"> }) {
  const t = useMessages(professionalQueryMessages);
  return (
    <div className="professional-facet-placeholder" aria-disabled="true">
      <span>{label}</span>
      <small>{state === "loading" ? t("读取中") : t("暂不可用")}</small>
    </div>
  );
}

export function GovernedFacetField({
  label,
  options,
  selected,
  state,
  onChange,
}: {
  label: string;
  options: FacetMultiSelectOption[];
  selected: string[];
  state: FacetCatalogState;
  onChange: (values: string[]) => void;
}) {
  if (state !== "ready") return <GovernedFacetPlaceholder label={label} state={state} />;
  if (!options.length) {
    // Empty governed catalogs are not a user-facing filter. Keep the form focused on conditions that can be used.
    return null;
  }
  return <FacetMultiSelect label={label} options={options} selected={selected} onChange={onChange} />;
}

export function GovernedFacetSelect({
  label,
  options,
  value,
  state,
  disabled = false,
  onChange,
}: {
  label: string;
  options: FacetMultiSelectOption[];
  value: string;
  state: FacetCatalogState;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const t = useMessages(professionalQueryMessages);
  if (state !== "ready") return <GovernedFacetPlaceholder label={label} state={state} />;
  if (!options.length) {
    // Empty governed catalogs are not a user-facing filter. Keep the form focused on conditions that can be used.
    return null;
  }
  return (
    <label>
      <span>{label}</span>
      <select aria-label={label} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t("全部")}</option>
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label} ({option.count})
          </option>
        ))}
      </select>
    </label>
  );
}

export function DateRange({
  label,
  from,
  to,
  onChange,
}: {
  label: string;
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}) {
  const t = useMessages(professionalQueryMessages);
  const [preset, setPreset] = useState<ProfessionalDatePreset>(() => identifyProfessionalDatePreset(from, to));

  useEffect(() => {
    setPreset(identifyProfessionalDatePreset(from, to));
  }, [from, to]);

  function selectPreset(value: ProfessionalDatePreset) {
    setPreset(value);
    if (value === "custom") return;
    const range = resolveProfessionalDatePreset(value);
    onChange(range.from, range.to);
  }

  return (
    <fieldset className="professional-date-range" aria-label={label}>
      <legend>{label}</legend>
      <label className="professional-date-preset">
        <span>{t("{label}时间范围", { label })}</span>
        <select
          aria-label={t("{label}时间范围", { label })}
          value={preset}
          onChange={(event) => selectPreset(event.target.value as ProfessionalDatePreset)}
        >
          <option value="all">{t("全部")}</option>
          <option value="last_month">{t("近 1 个月")}</option>
          <option value="last_6_months">{t("近半年")}</option>
          <option value="last_year">{t("近 1 年")}</option>
          <option value="custom">{t("自定义")}</option>
        </select>
      </label>
      {preset === "custom" ? (
        <div className="professional-custom-date-range">
          <label>
            <span>{t("起")}</span>
            <input type="date" value={from} onChange={(event) => onChange(event.target.value, to)} />
          </label>
          <label>
            <span>{t("止")}</span>
            <input type="date" value={to} onChange={(event) => onChange(from, event.target.value)} />
          </label>
        </div>
      ) : preset !== "all" ? (
        <output className="professional-date-output" aria-live="polite">
          {t("{from} 至 {to}", { from, to })}
        </output>
      ) : null}
    </fieldset>
  );
}
