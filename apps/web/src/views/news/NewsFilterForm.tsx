import { Search } from "lucide-react";
import { type FormEvent, useId } from "react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { NewsSearchFilters } from "../../lib/contracts/news";
import type { NewsEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { newsText as t } from "../../lib/i18n/news";
import { newsEntityTypes } from "../../lib/newsDisplay";
import { newsTypeLabel } from "./presentation";
export function NewsFilterForm({
  filters,
  eventTypes,
  publishers,
  languages,
  venues,
  facets,
  updateFilter,
  submit,
  clearFilters,
  querying,
  clearable,
  validationError,
}: {
  filters: NewsSearchFilters;
  eventTypes: string[];
  publishers: string[];
  languages: string[];
  venues: string[];
  facets: NewsEventSearchResult["facets"] | undefined;
  updateFilter: <K extends keyof NewsSearchFilters>(key: K, value: NewsSearchFilters[K]) => void;
  submit: (event: FormEvent) => void;
  clearFilters: () => void;
  querying: boolean;
  clearable: boolean;
  validationError: string;
}) {
  useLocale();
  const errorId = useId();
  return (
    <form className="domain-filter-bar news-filter-bar" onSubmit={submit} aria-label={t("新闻与会议筛选")}>
      <label className="domain-query-field">
        <span>{t("关键词")}</span>
        <span className="input-with-icon">
          <Search size={16} />
          <input
            value={filters.query}
            onChange={(event) => updateFilter("query", event.target.value)}
            placeholder={t("标题、摘要、公司、药物、靶点或疾病")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("事件类型")}</span>
        <select value={filters.eventType} onChange={(event) => updateFilter("eventType", event.target.value)}>
          <option value="">{t("全部")}</option>
          {eventTypes.map((value) => (
            <option value={value} key={value}>
              {newsTypeLabel(value)} ({facets?.event_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("发布方")}</span>
        <select value={filters.publisher} onChange={(event) => updateFilter("publisher", event.target.value)}>
          <option value="">{t("全部")}</option>
          {publishers.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.publisher?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <SecondaryFilters
        activeCount={
          [filters.entityId, filters.language, filters.venue, filters.publishedFrom, filters.publishedTo].filter(
            Boolean,
          ).length
        }
      >
        <EntityFilterSelect
          label={t("关联实体")}
          entityType={newsEntityTypes}
          value={filters.entityId}
          onChange={(entityId) => updateFilter("entityId", entityId)}
          placeholder={t("输入药品、靶点、疾病、机构或技术")}
        />
        <label>
          <span>{t("语言")}</span>
          <select value={filters.language} onChange={(event) => updateFilter("language", event.target.value)}>
            <option value="">{t("全部")}</option>
            {languages.map((value) => (
              <option value={value} key={value}>
                {value} ({facets?.language?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("会议 / 场景")}</span>
          <select value={filters.venue} onChange={(event) => updateFilter("venue", event.target.value)}>
            <option value="">{t("全部")}</option>
            {venues.map((value) => (
              <option value={value} key={value}>
                {value} ({facets?.venue?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("发布起始")}</span>
          <input
            type="date"
            value={filters.publishedFrom}
            aria-invalid={Boolean(validationError) || undefined}
            aria-describedby={validationError ? errorId : undefined}
            onChange={(event) => updateFilter("publishedFrom", event.target.value)}
          />
        </label>
        <label>
          <span>{t("发布截止")}</span>
          <input
            type="date"
            value={filters.publishedTo}
            aria-invalid={Boolean(validationError) || undefined}
            aria-describedby={validationError ? errorId : undefined}
            onChange={(event) => updateFilter("publishedTo", event.target.value)}
          />
        </label>
      </SecondaryFilters>
      {validationError ? (
        <p className="inline-error" id={errorId} role="alert">
          {validationError}
        </p>
      ) : null}
      <div className="domain-filter-actions">
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
