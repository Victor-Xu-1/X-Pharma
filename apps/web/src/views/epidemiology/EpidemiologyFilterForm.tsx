import { Search } from "lucide-react";
import type { FormEvent } from "react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { EpidemiologyFilters, EpidemiologySearchResult } from "../../lib/contracts/epidemiology";
import { epidemiologyMeasureLabels } from "../../lib/epidemiologyDisplay";
import { facetOptions } from "../../lib/facets";
import { useLocale } from "../../lib/i18n";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
import { measureValue, sexValue } from "./presentation";

const measureOrder = Object.keys(epidemiologyMeasureLabels);
export function EpidemiologyFilterForm({
  filters,
  data,
  setFilter,
  submit,
  clearFilters,
  querying,
  hasFilters,
}: {
  filters: EpidemiologyFilters;
  data: EpidemiologySearchResult | undefined;
  setFilter: <Key extends keyof EpidemiologyFilters>(key: Key, value: EpidemiologyFilters[Key]) => void;
  submit: (event: FormEvent) => void;
  clearFilters: () => void;
  querying: boolean;
  hasFilters: boolean;
}) {
  useLocale();
  const measureOptions = Array.from(
    new Set([...measureOrder, ...facetOptions(data?.facets, "measure", filters.measure)]),
  );
  const geographyOptions = facetOptions(data?.facets, "geography", filters.geography);
  const unitOptions = facetOptions(data?.facets, "unit", filters.unit);
  const patientPopulationOptions = data?.patient_populations ?? [];
  const populationOptions = facetOptions(data?.facets, "population_scope", filters.populationScope);
  const ageOptions = facetOptions(data?.facets, "age_group", filters.ageGroup);
  const sexOptions = facetOptions(data?.facets, "sex", filters.sex);

  return (
    <form className="domain-filter-bar epidemiology-filter-bar" onSubmit={submit} aria-label={t("流行病学筛选")}>
      <EntityFilterSelect
        label={t("疾病")}
        entityType="disease"
        value={filters.diseaseEntityId}
        onChange={(entityId) => setFilter("diseaseEntityId", entityId)}
        placeholder={t("输入疾病名称或别名")}
      />
      <label className="domain-query-field">
        <span>{t("来源或方法")}</span>
        <span className="input-with-icon">
          <Search size={16} />
          <input
            value={filters.query}
            onChange={(event) => setFilter("query", event.target.value)}
            placeholder={t("发布机构、方法学或观测编号")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("统计指标")}</span>
        <select value={filters.measure} onChange={(event) => setFilter("measure", event.target.value)}>
          <option value="">{t("全部")}</option>
          {measureOptions.map((value) => (
            <option value={value} key={value}>
              {measureValue(value)} ({data?.facets?.measure?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("地区")}</span>
        <select value={filters.geography} onChange={(event) => setFilter("geography", event.target.value)}>
          <option value="">{t("全部")}</option>
          {geographyOptions.map((value) => (
            <option value={value} key={value}>
              {value} ({data?.facets?.geography?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <SecondaryFilters
        activeCount={
          [
            filters.unit,
            filters.patientPopulationId,
            filters.populationScope,
            filters.ageGroup,
            filters.sex,
            filters.periodStartFrom,
            filters.periodEndTo,
          ].filter(Boolean).length
        }
      >
        <label>
          <span>{t("单位")}</span>
          <select value={filters.unit} onChange={(event) => setFilter("unit", event.target.value)}>
            <option value="">{t("全部")}</option>
            {unitOptions.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.unit?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("标准患者人群")}</span>
          <select
            value={filters.patientPopulationId}
            onChange={(event) => setFilter("patientPopulationId", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {patientPopulationOptions.map((option) => (
              <option value={option.id} key={option.id}>
                {option.name} ({option.count})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("人群口径")}</span>
          <select
            value={filters.populationScope}
            onChange={(event) => setFilter("populationScope", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {populationOptions.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.population_scope?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("年龄组")}</span>
          <select value={filters.ageGroup} onChange={(event) => setFilter("ageGroup", event.target.value)}>
            <option value="">{t("全部")}</option>
            {ageOptions.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.age_group?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("性别")}</span>
          <select value={filters.sex} onChange={(event) => setFilter("sex", event.target.value)}>
            <option value="">{t("全部")}</option>
            {sexOptions.map((value) => (
              <option value={value} key={value}>
                {sexValue(value)} ({data?.facets?.sex?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("观察期起")}</span>
          <input
            type="date"
            value={filters.periodStartFrom}
            onChange={(event) => setFilter("periodStartFrom", event.target.value)}
          />
        </label>
        <label>
          <span>{t("观察期止")}</span>
          <input
            type="date"
            value={filters.periodEndTo}
            min={filters.periodStartFrom || undefined}
            onChange={(event) => setFilter("periodEndTo", event.target.value)}
          />
        </label>
      </SecondaryFilters>
      <div className="domain-filter-actions">
        <button className="primary-button" type="submit" disabled={querying}>
          <Search size={16} />
          {t("查询")}
        </button>
        <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
          {t("清除")}
        </button>
      </div>
    </form>
  );
}
