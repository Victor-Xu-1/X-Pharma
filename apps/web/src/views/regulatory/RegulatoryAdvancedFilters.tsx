import type { RegulatorySearchFilters } from "../../lib/contracts/regulatory";
import type { RegulatoryEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
import {
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  regulatoryStatusLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../../lib/regulatoryDisplay";
import { regulatoryValue as displayValue } from "./presentation";
import { RegulatoryDateRange } from "./RegulatoryDateRange";
export function RegulatoryAdvancedFilters({
  filters,
  facets,
  eventTypes,
  statuses,
  updateFilter,
}: {
  filters: RegulatorySearchFilters;
  facets: RegulatoryEventSearchResult["facets"] | undefined;
  eventTypes: string[];
  statuses: string[];
  updateFilter: <K extends keyof RegulatorySearchFilters>(key: K, value: RegulatorySearchFilters[K]) => void;
}) {
  useLocale();
  return (
    <>
      <label>
        <span>{t("事件类型")}</span>
        <select value={filters.eventType} onChange={(event) => updateFilter("eventType", event.target.value)}>
          <option value="">{t("全部")}</option>
          {eventTypes.map((value) => (
            <option value={value} key={value}>
              {displayValue(value, eventTypeLabels)} ({facets?.event_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("认定资格")}</span>
        <select
          value={filters.designationType}
          onChange={(event) => updateFilter("designationType", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.entries(designationLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({facets?.designation_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("事件状态")}</span>
        <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
          <option value="">{t("全部")}</option>
          {statuses.map((value) => (
            <option value={value} key={value}>
              {displayValue(value, regulatoryStatusLabels)} ({facets?.status?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("标签变更")}</span>
        <select
          value={filters.labelChangeType}
          onChange={(event) => updateFilter("labelChangeType", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.entries(labelChangeLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({facets?.label_change_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("黑框警告")}</span>
        <select
          aria-label={t("黑框警告")}
          value={filters.boxedWarning}
          onChange={(event) => updateFilter("boxedWarning", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          <option value="true">
            {t("有")} ({facets?.has_boxed_warning?.true ?? 0})
          </option>
          <option value="false">
            {t("无")} ({facets?.has_boxed_warning?.false ?? 0})
          </option>
        </select>
      </label>

      <label>
        <span>{t("安全信号")}</span>
        <select
          aria-label={t("安全信号")}
          value={filters.safetySignalType}
          onChange={(event) => updateFilter("safetySignalType", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.entries(safetySignalLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({facets?.safety_signal_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("严重程度")}</span>
        <select value={filters.safetySeverity} onChange={(event) => updateFilter("safetySeverity", event.target.value)}>
          <option value="">{t("全部")}</option>
          {Object.entries(severityLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({facets?.safety_severity?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("信号状态")}</span>
        <select value={filters.safetyStatus} onChange={(event) => updateFilter("safetyStatus", event.target.value)}>
          <option value="">{t("全部")}</option>
          {Object.entries(safetyStatusLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({facets?.safety_status?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>

      <RegulatoryDateRange
        label={t("决定日期")}
        from={filters.decisionFrom}
        to={filters.decisionTo}
        onFrom={(value) => updateFilter("decisionFrom", value)}
        onTo={(value) => updateFilter("decisionTo", value)}
      />

      <RegulatoryDateRange
        label={t("来源更新")}
        from={filters.sourceUpdatedFrom}
        to={filters.sourceUpdatedTo}
        onFrom={(value) => updateFilter("sourceUpdatedFrom", value)}
        onTo={(value) => updateFilter("sourceUpdatedTo", value)}
      />
    </>
  );
}
