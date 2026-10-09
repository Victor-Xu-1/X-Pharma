import { Search } from "lucide-react";
import type { FormEvent } from "react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { PatentSearchFilters } from "../../lib/contracts/patents";
import { facetOptions } from "../../lib/facets";
import type { EntityType, PatentFamilySearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { patentText as t } from "../../lib/i18n/patents";
import { patentStatus } from "../../lib/patentDisplay";

export const patentEntityTypes = ["target", "drug", "disease", "organization"] as const satisfies readonly EntityType[];
export type PatentEntityType = (typeof patentEntityTypes)[number];

function DateRange({
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

export function PatentFilterForm({
  filters,
  facets,
  entityType,
  onEntityType,
  update,
  submit,
  clear,
  querying,
  clearable,
  validationError,
}: {
  filters: PatentSearchFilters;
  facets: PatentFamilySearchResult["facets"] | undefined;
  entityType: PatentEntityType;
  onEntityType: (value: PatentEntityType) => void;
  update: <K extends keyof PatentSearchFilters>(key: K, value: PatentSearchFilters[K]) => void;
  submit: (event: FormEvent) => void;
  clear: () => void;
  querying: boolean;
  clearable: boolean;
  validationError: string;
}) {
  useLocale();
  return (
    <form className="domain-filter-bar patent-filter-bar" onSubmit={submit} aria-label={t("专利族筛选")}>
      <label className="domain-query-field">
        <span>{t("关键词")}</span>
        <span className="input-with-icon">
          <Search size={16} aria-hidden="true" />
          <input
            value={filters.query}
            onChange={(event) => update("query", event.target.value)}
            placeholder={t("专利族号、标题、申请人或公开文本")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("申请人")}</span>
        <select
          aria-label={t("申请人")}
          value={filters.applicant}
          onChange={(event) => update("applicant", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {facetOptions(facets, "applicant", filters.applicant).map((value) => (
            <option key={value} value={value}>
              {value} ({facets?.applicant?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("法律状态")}</span>
        <select
          aria-label={t("法律状态")}
          value={filters.legalStatus}
          onChange={(event) => update("legalStatus", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {facetOptions(facets, "legal_status", filters.legalStatus).map((value) => (
            <option key={value} value={value}>
              {patentStatus(value)} ({facets?.legal_status?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <SecondaryFilters
        label={t("更多专利条件")}
        activeCount={
          [
            filters.entityId,
            filters.priorityFrom,
            filters.priorityTo,
            filters.expirationFrom,
            filters.expirationTo,
          ].filter(Boolean).length
        }
      >
        <label>
          <span>{t("关联实体类型")}</span>
          <select value={entityType} onChange={(event) => onEntityType(event.target.value as PatentEntityType)}>
            <option value="target">{t("靶点")}</option>
            <option value="drug">{t("药品")}</option>
            <option value="disease">{t("疾病/适应症")}</option>
            <option value="organization">{t("机构")}</option>
          </select>
        </label>
        <EntityFilterSelect
          label={t("关联实体")}
          entityType={entityType}
          value={filters.entityId}
          onChange={(value) => update("entityId", value)}
          placeholder={t("输入药品、靶点、适应症或机构")}
        />
        <DateRange
          label={t("优先权日期")}
          from={filters.priorityFrom}
          to={filters.priorityTo}
          onFrom={(value) => update("priorityFrom", value)}
          onTo={(value) => update("priorityTo", value)}
        />
        <DateRange
          label={t("预计到期日期")}
          from={filters.expirationFrom}
          to={filters.expirationTo}
          onFrom={(value) => update("expirationFrom", value)}
          onTo={(value) => update("expirationTo", value)}
        />
      </SecondaryFilters>
      {validationError ? (
        <p className="form-error patent-filter-error" role="alert">
          {validationError}
        </p>
      ) : null}
      <div className="domain-filter-actions patent-filter-actions">
        <button className="primary-button" type="submit" disabled={querying}>
          <Search size={16} aria-hidden="true" />
          {t("查询")}
        </button>
        <button className="secondary-button" type="button" onClick={clear} disabled={!clearable}>
          {t("清除")}
        </button>
      </div>
    </form>
  );
}
