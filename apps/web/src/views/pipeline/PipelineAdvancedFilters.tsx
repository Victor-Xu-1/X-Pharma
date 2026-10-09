import { ChevronDown } from "lucide-react";
import { FacetMultiSelect } from "../../components/FacetMultiSelect";
import { pipelineText as t } from "../../lib/i18n/pipeline";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedDevelopmentPhase, localizedProgramTag } from "../../lib/i18n/programVocabulary";
import { pipelineFilterOptions } from "./filterOptions";
import type { PipelineFilterProps } from "./filterTypes";
import { PipelineDateRange } from "./PipelineDateRange";
import { organizationRoleLabels } from "./ProgramCells";
export function PipelineAdvancedFilters({ filters, updateFilter, data }: PipelineFilterProps) {
  const {
    globalPhases,
    chinaPhases,
    developmentRights,
    commercializationRights,
    programTags,
    milestoneTypes,
    organizationTypes,
    organizationCountries,
  } = pipelineFilterOptions(data, filters);
  const advancedCount = [
    filters.globalPhase,
    filters.organizationRole,
    filters.organizationType,
    filters.organizationCountryRegion,
    filters.chinaPhase,
    filters.globalPhaseStartedFrom,
    filters.globalPhaseStartedTo,
    filters.chinaPhaseStartedFrom,
    filters.chinaPhaseStartedTo,
    filters.developmentRightsRegion,
    filters.commercializationRightsRegion,
    filters.programTags.length,
    filters.milestoneType,
    filters.milestoneFrom,
    filters.milestoneTo,
    filters.statusDateFrom,
    filters.statusDateTo,
  ].filter(Boolean).length;
  return (
    <details className="advanced-filter-panel pipeline-advanced-filters" open={advancedCount > 0 || undefined}>
      <summary>
        <span>{t("机构、区域阶段、权益与里程碑")}</span>
        <small>{advancedCount ? t("已选 {count} 项", { count: advancedCount }) : t("按需展开")}</small>
        <ChevronDown className="disclosure-chevron" size={16} aria-hidden="true" />
      </summary>
      <div className="pipeline-advanced-grid">
        <label>
          <span>{t("机构角色")}</span>
          <select
            value={filters.organizationRole}
            onChange={(event) => updateFilter("organizationRole", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {Object.entries(organizationRoleLabels).map(([value, label]) => (
              <option value={value} key={value}>
                {professionalEnumLabel(label, value)} ({data?.facets?.organization_role?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("机构类型")}</span>
          <select
            value={filters.organizationType}
            onChange={(event) => updateFilter("organizationType", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {organizationTypes.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.organization_type?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("机构所在地区")}</span>
          <select
            value={filters.organizationCountryRegion}
            onChange={(event) => updateFilter("organizationCountryRegion", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {organizationCountries.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.organization_country_region?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("全球最高阶段")}</span>
          <select value={filters.globalPhase} onChange={(event) => updateFilter("globalPhase", event.target.value)}>
            <option value="">{t("全部")}</option>
            {globalPhases.map((value) => (
              <option value={value} key={value}>
                {localizedDevelopmentPhase(value)} ({data?.facets?.global_phase?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("中国最高阶段")}</span>
          <select value={filters.chinaPhase} onChange={(event) => updateFilter("chinaPhase", event.target.value)}>
            <option value="">{t("全部")}</option>
            {chinaPhases.map((value) => (
              <option value={value} key={value}>
                {localizedDevelopmentPhase(value)} ({data?.facets?.china_phase?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("研发权益地区")}</span>
          <select
            value={filters.developmentRightsRegion}
            onChange={(event) => updateFilter("developmentRightsRegion", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {developmentRights.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.development_rights_region?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("商业化权益地区")}</span>
          <select
            value={filters.commercializationRightsRegion}
            onChange={(event) => updateFilter("commercializationRightsRegion", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {commercializationRights.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.commercialization_rights_region?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        {programTags.length || filters.programTags.length ? (
          <FacetMultiSelect
            label={t("项目标签")}
            options={programTags.map((value) => ({
              value,
              label: localizedProgramTag(value),
              count: data?.facets?.program_tag?.[value] ?? 0,
            }))}
            selected={filters.programTags}
            onChange={(values) => updateFilter("programTags", values)}
          />
        ) : null}
        <label>
          <span>{t("里程碑类型")}</span>
          <select value={filters.milestoneType} onChange={(event) => updateFilter("milestoneType", event.target.value)}>
            <option value="">{t("全部")}</option>
            {milestoneTypes.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.milestone_type?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <PipelineDateRange
          label={t("全球阶段起始日期")}
          from={filters.globalPhaseStartedFrom}
          to={filters.globalPhaseStartedTo}
          onFromChange={(value) => updateFilter("globalPhaseStartedFrom", value)}
          onToChange={(value) => updateFilter("globalPhaseStartedTo", value)}
        />
        <PipelineDateRange
          label={t("中国阶段起始日期")}
          from={filters.chinaPhaseStartedFrom}
          to={filters.chinaPhaseStartedTo}
          onFromChange={(value) => updateFilter("chinaPhaseStartedFrom", value)}
          onToChange={(value) => updateFilter("chinaPhaseStartedTo", value)}
        />
        <PipelineDateRange
          label={t("里程碑日期")}
          from={filters.milestoneFrom}
          to={filters.milestoneTo}
          onFromChange={(value) => updateFilter("milestoneFrom", value)}
          onToChange={(value) => updateFilter("milestoneTo", value)}
        />
        <PipelineDateRange
          label={t("状态更新日期")}
          from={filters.statusDateFrom}
          to={filters.statusDateTo}
          onFromChange={(value) => updateFilter("statusDateFrom", value)}
          onToChange={(value) => updateFilter("statusDateTo", value)}
        />
      </div>
    </details>
  );
}
