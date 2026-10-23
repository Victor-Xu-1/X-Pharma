import { FacetMultiSelect } from "../../components/FacetMultiSelect";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedProgramModality } from "../../lib/i18n/programVocabulary";
import { trialLinkedPhaseLabels as developmentPhaseLabels } from "../../lib/phasePresentation";
import { trialFilterOptions } from "./filterOptions";
import type { TrialFilterProps } from "./filterTypes";
export function TrialLinkedProgramFilters({
  filters,
  setters,
  data,
  linkedProgramFiltersOpen,
  setLinkedProgramFiltersOpen,
}: TrialFilterProps & { linkedProgramFiltersOpen: boolean; setLinkedProgramFiltersOpen: (open: boolean) => void }) {
  const {
    linkedDrugModalities,
    linkedDrugInnovationTypes,
    linkedDrugCategories,
    linkedDrugProgramTags,
    linkedDrugGlobalPhase,
    linkedDrugOrganizationCountryRegion,
  } = filters;
  const {
    setLinkedDrugModalities,
    setLinkedDrugInnovationTypes,
    setLinkedDrugCategories,
    setLinkedDrugProgramTags,
    setLinkedDrugGlobalPhase,
    setLinkedDrugOrganizationCountryRegion,
  } = setters;
  const {
    linkedDrugModalityOptions,
    linkedDrugInnovationTypeOptions,
    linkedDrugCategoryOptions,
    linkedDrugProgramTagOptions,
    linkedDrugGlobalPhases,
    linkedDrugOrganizationCountries,
  } = trialFilterOptions(data, filters);
  return (
    <details
      className="advanced-filters trial-linked-program-filters"
      open={linkedProgramFiltersOpen}
      onToggle={(event) => setLinkedProgramFiltersOpen(event.currentTarget.open)}
    >
      <summary>
        {t("关联药物属性")}
        <span>{t("同一药物项目")}</span>
      </summary>
      <div className="trial-linked-program-grid">
        <FacetMultiSelect
          label="Modality"
          options={linkedDrugModalityOptions.map((value) => ({
            value,
            label: localizedProgramModality(value),
            count: data?.facets?.linked_drug_modality?.[value] ?? 0,
          }))}
          selected={linkedDrugModalities}
          onChange={setLinkedDrugModalities}
        />
        <FacetMultiSelect
          label={t("创新类型")}
          options={linkedDrugInnovationTypeOptions.map((value) => ({
            value,
            label: value,
            count: data?.facets?.linked_drug_innovation_type?.[value] ?? 0,
          }))}
          selected={linkedDrugInnovationTypes}
          onChange={setLinkedDrugInnovationTypes}
        />
        <FacetMultiSelect
          label={t("药品类别")}
          options={linkedDrugCategoryOptions.map((value) => ({
            value,
            label: value,
            count: data?.facets?.linked_drug_category?.[value] ?? 0,
          }))}
          selected={linkedDrugCategories}
          onChange={setLinkedDrugCategories}
        />
        <FacetMultiSelect
          label={t("药品标签")}
          options={linkedDrugProgramTagOptions.map((value) => ({
            value,
            label: value,
            count: data?.facets?.linked_drug_program_tag?.[value] ?? 0,
          }))}
          selected={linkedDrugProgramTags}
          onChange={setLinkedDrugProgramTags}
        />
        <label>
          <span>{t("全球最高阶段")}</span>
          <select value={linkedDrugGlobalPhase} onChange={(event) => setLinkedDrugGlobalPhase(event.target.value)}>
            <option value="">{t("全部")}</option>
            {linkedDrugGlobalPhases.map((value) => (
              <option value={value} key={value}>
                {developmentPhaseLabels[value] ? professionalEnumLabel(developmentPhaseLabels[value], value) : value} (
                {data?.facets?.linked_drug_global_phase?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("研发机构国家/地区")}</span>
          <select
            value={linkedDrugOrganizationCountryRegion}
            onChange={(event) => setLinkedDrugOrganizationCountryRegion(event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {linkedDrugOrganizationCountries.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.linked_drug_organization_country_region?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
      </div>
    </details>
  );
}
