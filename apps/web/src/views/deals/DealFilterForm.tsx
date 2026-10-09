import { Search } from "lucide-react";
import type { FormEvent } from "react";
import type { DealSearchFilters } from "../../lib/contracts/deals";
import { dealLabel, dealTypeLabels, statusLabels } from "../../lib/dealDisplay";
import { facetOptions } from "../../lib/facets";
import type { EntityRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { DealAdvancedFilters } from "./DealAdvancedFilters";
import { DealParticipantFilters } from "./DealParticipantFilters";

export function DealFilterForm({
  filters,
  facets,
  suggestions,
  suggestionsEnabled,
  suggestionsLoading,
  updateFilter,
  onPartyText,
  chooseParty,
  submit,
  clearFilters,
  querying,
  clearable,
  validationError,
}: {
  filters: DealSearchFilters;
  facets: Record<string, Record<string, number>> | undefined;
  suggestions: readonly EntityRead[];
  suggestionsEnabled: boolean;
  suggestionsLoading: boolean;
  updateFilter: <K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) => void;
  onPartyText: (value: string) => void;
  chooseParty: (id: string, name: string) => void;
  submit: (event: FormEvent) => void;
  clearFilters: () => void;
  querying: boolean;
  clearable: boolean;
  validationError: string;
}) {
  useLocale();
  const dealTypes = facetOptions(facets, "deal_type", filters.dealType);
  const statusOptions = facetOptions(facets, "status", [filters.status, ...Object.keys(statusLabels)]);
  return (
    <form className="domain-filter-bar deal-filter-bar" onSubmit={submit} aria-label={t("交易筛选")}>
      <label className="domain-query-field">
        <span>{t("关键词")}</span>
        <span className="input-with-icon">
          <Search size={16} />
          <input
            value={filters.query}
            onChange={(event) => updateFilter("query", event.target.value)}
            placeholder={t("交易名称、公司、资产或条款")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("交易类型")}</span>
        <select value={filters.dealType} onChange={(event) => updateFilter("dealType", event.target.value)}>
          <option value="">{t("全部")}</option>
          {dealTypes.map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, dealTypeLabels)} ({facets?.deal_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("交易状态")}</span>
        <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
          <option value="">{t("全部")}</option>
          {statusOptions.map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, statusLabels)} ({facets?.status?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <DealParticipantFilters
        filters={filters}
        facets={facets}
        suggestions={suggestions}
        suggestionsEnabled={suggestionsEnabled}
        loading={suggestionsLoading}
        onChange={updateFilter}
        onPartyText={onPartyText}
        onChooseParty={chooseParty}
      />

      <DealAdvancedFilters filters={filters} facets={facets} updateFilter={updateFilter} />

      {validationError ? (
        <p className="form-error deal-filter-error" role="alert">
          {validationError}
        </p>
      ) : null}
      <div className="domain-filter-actions deal-filter-actions">
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
