import { SecondaryFilters } from "../../components/SecondaryFilters";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import {
  trialInitiationTypeLabels as initiationTypeLabels,
  trialTherapyLineLabels as therapyLineLabels,
} from "../../lib/trialFilters";
import { trialFilterOptions } from "./filterOptions";
import type { TrialFilterProps } from "./filterTypes";
export function TrialDesignFilters({ filters, setters, data }: TrialFilterProps) {
  const { registry, studyType, acronym, initiationType, therapyLine } = filters;
  const { setRegistry, setStudyType, setAcronym, setInitiationType, setTherapyLine } = setters;
  const { registries, studyTypes } = trialFilterOptions(data, filters);
  return (
    <SecondaryFilters
      label={t("试验设计与注册信息")}
      activeCount={[registry, studyType, acronym, initiationType, therapyLine].filter(Boolean).length}
    >
      <label>
        <span>{t("注册平台")}</span>
        <select value={registry} onChange={(event) => setRegistry(event.target.value)}>
          <option value="">{t("全部")}</option>
          {registries.map((value) => (
            <option value={value} key={value}>
              {value} ({data?.facets?.registry?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("研究类型")}</span>
        <select value={studyType} onChange={(event) => setStudyType(event.target.value)}>
          <option value="">{t("全部")}</option>
          {studyTypes.map((value) => (
            <option value={value} key={value}>
              {localizedTrialStudyType(value)} ({data?.facets?.study_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("试验简称")}</span>
        <input
          value={acronym}
          onChange={(event) => setAcronym(event.target.value)}
          placeholder={t("如 KEYNOTE、CheckMate")}
          maxLength={240}
        />
      </label>
      <label>
        <span>{t("发起类型")}</span>
        <select value={initiationType} onChange={(event) => setInitiationType(event.target.value)}>
          <option value="">{t("全部")}</option>
          {Object.entries(initiationTypeLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({data?.facets?.initiation_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("治疗线次")}</span>
        <select value={therapyLine} onChange={(event) => setTherapyLine(event.target.value)}>
          <option value="">{t("全部")}</option>
          {Object.entries(therapyLineLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({data?.facets?.therapy_line?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
    </SecondaryFilters>
  );
}
