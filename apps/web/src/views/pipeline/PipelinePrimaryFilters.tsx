import { Search } from "lucide-react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { FacetMultiSelect } from "../../components/FacetMultiSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import { pipelineText as t } from "../../lib/i18n/pipeline";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedDevelopmentPhase, localizedProgramModality } from "../../lib/i18n/programVocabulary";
import { programStatusLabels } from "./filterLabels";
import { pipelineFilterOptions } from "./filterOptions";
import type { PipelineFilterProps } from "./filterTypes";
export function PipelinePrimaryFilters({
  filters,
  updateFilter,
  data,
  rememberEntity,
}: PipelineFilterProps & { rememberEntity: (field: string, id: string, name?: string) => void }) {
  const { modalities, innovationTypes, therapeuticAreas, drugCategories, phases, geographies } = pipelineFilterOptions(
    data,
    filters,
  );
  return (
    <>
      <div className="pipeline-primary-filters">
        <label className="domain-query-field">
          <span>{t("关键词")}</span>
          <span className="input-with-icon">
            <Search size={16} />
            <input
              value={filters.query}
              onChange={(event) => updateFilter("query", event.target.value)}
              placeholder={t("药物、作用机制或项目名称")}
              maxLength={500}
            />
          </span>
        </label>
        <FacetMultiSelect
          label={t("药物类型")}
          options={modalities.map((value) => ({
            value,
            label: localizedProgramModality(value),
            count: data?.facets?.modality?.[value] ?? 0,
          }))}
          selected={filters.modalities}
          onChange={(values) => updateFilter("modalities", values)}
        />
        <label>
          <span>{t("项目状态")}</span>
          <select value={filters.programStatus} onChange={(event) => updateFilter("programStatus", event.target.value)}>
            <option value="">{t("全部")}</option>
            {(["active", "inactive", "unknown"] as const).map((value) => (
              <option
                value={value}
                key={value}
                disabled={
                  !filters.programStatus || filters.programStatus !== value
                    ? (data?.facets?.program_status?.[value] ?? 0) === 0
                    : false
                }
              >
                {professionalEnumLabel(programStatusLabels[value], value)} ({data?.facets?.program_status?.[value] ?? 0}
                )
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("总体最高阶段")}</span>
          <select value={filters.phase} onChange={(event) => updateFilter("phase", event.target.value)}>
            <option value="">{t("全部")}</option>
            {phases.map((value) => (
              <option value={value} key={value}>
                {localizedDevelopmentPhase(value)} ({data?.facets?.phase?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="pipeline-entity-filters" aria-label={t("药品、靶点、适应症与研发机构")}>
        <EntityFilterSelect
          label={t("药品")}
          entityType="drug"
          value={filters.drugEntityId}
          placeholder={t("输入规范药品")}
          onChange={(entityId, name) => {
            updateFilter("drugEntityId", entityId);
            rememberEntity("drug_entity_id", entityId, name);
          }}
          onResolved={(entityId, name) => rememberEntity("drug_entity_id", entityId, name)}
        />
        <EntityFilterSelect
          label={t("靶点")}
          entityType="target"
          value={filters.targetEntityId}
          placeholder={t("输入至少 2 个字符")}
          onChange={(entityId, name) => {
            updateFilter("targetEntityId", entityId);
            rememberEntity("target_entity_id", entityId, name);
          }}
          onResolved={(entityId, name) => rememberEntity("target_entity_id", entityId, name)}
        />
        <EntityFilterSelect
          label={t("适应症")}
          entityType="disease"
          value={filters.diseaseEntityId}
          placeholder={t("输入疾病或适应症")}
          onChange={(entityId, name) => {
            updateFilter("diseaseEntityId", entityId);
            rememberEntity("disease_entity_id", entityId, name);
          }}
          onResolved={(entityId, name) => rememberEntity("disease_entity_id", entityId, name)}
        />
        <EntityFilterSelect
          label={t("研发机构")}
          entityType="organization"
          value={filters.organizationEntityId}
          placeholder={t("输入机构名称")}
          onChange={(entityId, name) => {
            updateFilter("organizationEntityId", entityId);
            rememberEntity("organization_entity_id", entityId, name);
          }}
          onResolved={(entityId, name) => rememberEntity("organization_entity_id", entityId, name)}
        />
      </fieldset>

      <SecondaryFilters
        label={t("药物分类与记录地区")}
        activeCount={
          [
            filters.innovationTypes.length,
            filters.therapeuticAreas.length,
            filters.drugCategories.length,
            filters.geography,
          ].filter(Boolean).length
        }
      >
        <FacetMultiSelect
          label={t("创新类型")}
          options={innovationTypes.map((value) => ({
            value,
            label: value,
            count: data?.facets?.innovation_type?.[value] ?? 0,
          }))}
          selected={filters.innovationTypes}
          onChange={(values) => updateFilter("innovationTypes", values)}
        />
        <FacetMultiSelect
          label={t("适应症领域")}
          options={therapeuticAreas.map((value) => ({
            value,
            label: value,
            count: data?.facets?.therapeutic_area?.[value] ?? 0,
          }))}
          selected={filters.therapeuticAreas}
          onChange={(values) => updateFilter("therapeuticAreas", values)}
        />
        <FacetMultiSelect
          label={t("药品类别")}
          options={drugCategories.map((value) => ({
            value,
            label: value,
            count: data?.facets?.drug_category?.[value] ?? 0,
          }))}
          selected={filters.drugCategories}
          onChange={(values) => updateFilter("drugCategories", values)}
        />
        <label>
          <span>{t("记录地区")}</span>
          <select value={filters.geography} onChange={(event) => updateFilter("geography", event.target.value)}>
            <option value="">{t("全部")}</option>
            {geographies.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.geography?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
      </SecondaryFilters>
    </>
  );
}
