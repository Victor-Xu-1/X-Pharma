import { Search } from "lucide-react";
import type { FormEvent } from "react";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { RegulatorySearchFilters } from "../../lib/contracts/regulatory";
import type { RegulatoryEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
import { RegulatoryAdvancedFilters } from "./RegulatoryAdvancedFilters";

export function RegulatoryFilterForm({
  filters,
  facets,
  agencies,
  jurisdictions,
  eventTypes,
  statuses,
  updateFilter,
  submit,
  clearFilters,
  querying,
  clearable,
  validationError,
}: {
  filters: RegulatorySearchFilters;
  facets: RegulatoryEventSearchResult["facets"] | undefined;
  agencies: string[];
  jurisdictions: string[];
  eventTypes: string[];
  statuses: string[];
  updateFilter: <K extends keyof RegulatorySearchFilters>(key: K, value: RegulatorySearchFilters[K]) => void;
  submit: (event: FormEvent) => void;
  clearFilters: () => void;
  querying: boolean;
  clearable: boolean;
  validationError: string;
}) {
  useLocale();
  return (
    <form className="domain-filter-bar regulatory-filter-bar" onSubmit={submit} aria-label={t("监管事件筛选")}>
      <label className="domain-query-field">
        <span>{t("关键词")}</span>
        <span className="input-with-icon">
          <Search size={16} />
          <input
            value={filters.query}
            onChange={(event) => updateFilter("query", event.target.value)}
            placeholder={t("药物、适应症、申请号、标签或安全术语")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("监管机构")}</span>
        <select value={filters.agency} onChange={(event) => updateFilter("agency", event.target.value)}>
          <option value="">{t("全部")}</option>
          {agencies.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.agency?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("辖区")}</span>
        <select value={filters.jurisdiction} onChange={(event) => updateFilter("jurisdiction", event.target.value)}>
          <option value="">{t("全部")}</option>
          {jurisdictions.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.jurisdiction?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <SecondaryFilters
        label={t("更多监管与安全条件")}
        activeCount={
          [
            filters.eventType,
            filters.designationType,
            filters.status,
            filters.labelChangeType,
            filters.boxedWarning,
            filters.safetySignalType,
            filters.safetySeverity,
            filters.safetyStatus,
            filters.decisionFrom,
            filters.decisionTo,
            filters.sourceUpdatedFrom,
            filters.sourceUpdatedTo,
          ].filter(Boolean).length
        }
      >
        <RegulatoryAdvancedFilters
          filters={filters}
          facets={facets}
          eventTypes={eventTypes}
          statuses={statuses}
          updateFilter={updateFilter}
        />
      </SecondaryFilters>

      {validationError ? (
        <p className="form-error regulatory-filter-error" role="alert">
          {validationError}
        </p>
      ) : null}
      <div className="domain-filter-actions regulatory-filter-actions">
        <button className="primary-button" type="submit" disabled={querying}>
          <Search size={16} />
          {t("查询")}
        </button>
        <button className="secondary-button" type="button" onClick={clearFilters} disabled={!clearable}>
          {t("清除")}
        </button>
      </div>
    </form>
  );
}
