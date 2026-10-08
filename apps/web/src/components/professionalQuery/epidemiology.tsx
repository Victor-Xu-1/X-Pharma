import { RefreshCw } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import { EntityFilterSelect } from "../EntityFilterSelect";
import { DateRange, GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "epidemiologyCatalog"
  | "epidemiologyCatalogState"
  | "epidemiologyMeasureOptions"
  | "epidemiologyGeographyOptions"
  | "epidemiologyUnitOptions"
  | "epidemiologyPopulationScopeOptions"
  | "epidemiologyAgeGroupOptions"
  | "epidemiologySexOptions"
  | "epidemiologyPatientPopulationOptions"
  | "draft"
  | "update"
  | "updateDateRange"
>;

export function EpidemiologyFields({
  epidemiologyCatalog,
  epidemiologyCatalogState,
  epidemiologyMeasureOptions,
  epidemiologyGeographyOptions,
  epidemiologyUnitOptions,
  epidemiologyPopulationScopeOptions,
  epidemiologyAgeGroupOptions,
  epidemiologySexOptions,
  epidemiologyPatientPopulationOptions,
  draft,
  update,
  updateDateRange,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      <EntityFilterSelect
        label={t("疾病")}
        entityType="disease"
        value={draft.diseaseEntityId}
        onChange={(value) => update("diseaseEntityId", value)}
        placeholder={t("输入疾病名称或别名")}
      />
      {epidemiologyCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          {t("正在读取流行病学筛选选项")}
        </div>
      ) : null}
      {epidemiologyCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>{t("流行病学筛选选项暂不可用")}</span>
          <button type="button" className="text-button" onClick={() => void epidemiologyCatalog.refetch()}>
            <RefreshCw size={13} />
            {t("重试")}
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label={t("统计指标")}
        options={epidemiologyMeasureOptions}
        value={draft.epidemiologyMeasure}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyMeasure", value)}
      />
      <GovernedFacetSelect
        label={t("地区")}
        options={epidemiologyGeographyOptions}
        value={draft.epidemiologyGeography}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyGeography", value)}
      />
      <GovernedFacetSelect
        label={t("单位")}
        options={epidemiologyUnitOptions}
        value={draft.epidemiologyUnit}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyUnit", value)}
      />
      <GovernedFacetSelect
        label={t("标准患者人群")}
        options={epidemiologyPatientPopulationOptions}
        value={draft.epidemiologyPatientPopulationId}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyPatientPopulationId", value)}
      />
      <GovernedFacetSelect
        label={t("人群口径")}
        options={epidemiologyPopulationScopeOptions}
        value={draft.epidemiologyPopulationScope}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyPopulationScope", value)}
      />
      <GovernedFacetSelect
        label={t("年龄组")}
        options={epidemiologyAgeGroupOptions}
        value={draft.epidemiologyAgeGroup}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyAgeGroup", value)}
      />
      <GovernedFacetSelect
        label={t("性别")}
        options={epidemiologySexOptions}
        value={draft.epidemiologySex}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologySex", value)}
      />
      <DateRange
        label={t("统计周期")}
        from={draft.epidemiologyPeriodStartFrom}
        to={draft.epidemiologyPeriodEndTo}
        onChange={(from, to) => updateDateRange("epidemiologyPeriodStartFrom", "epidemiologyPeriodEndTo", from, to)}
      />
    </>
  );
}
