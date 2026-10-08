import { RefreshCw } from "lucide-react";
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
  return (
    <>
      <EntityFilterSelect
        label="疾病"
        entityType="disease"
        value={draft.diseaseEntityId}
        onChange={(value) => update("diseaseEntityId", value)}
        placeholder="输入疾病名称或别名"
      />
      {epidemiologyCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          正在读取流行病学筛选选项
        </div>
      ) : null}
      {epidemiologyCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>流行病学筛选选项暂不可用</span>
          <button type="button" className="text-button" onClick={() => void epidemiologyCatalog.refetch()}>
            <RefreshCw size={13} />
            重试
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label="统计指标"
        options={epidemiologyMeasureOptions}
        value={draft.epidemiologyMeasure}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyMeasure", value)}
      />
      <GovernedFacetSelect
        label="地区"
        options={epidemiologyGeographyOptions}
        value={draft.epidemiologyGeography}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyGeography", value)}
      />
      <GovernedFacetSelect
        label="单位"
        options={epidemiologyUnitOptions}
        value={draft.epidemiologyUnit}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyUnit", value)}
      />
      <GovernedFacetSelect
        label="标准患者人群"
        options={epidemiologyPatientPopulationOptions}
        value={draft.epidemiologyPatientPopulationId}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyPatientPopulationId", value)}
      />
      <GovernedFacetSelect
        label="人群口径"
        options={epidemiologyPopulationScopeOptions}
        value={draft.epidemiologyPopulationScope}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyPopulationScope", value)}
      />
      <GovernedFacetSelect
        label="年龄组"
        options={epidemiologyAgeGroupOptions}
        value={draft.epidemiologyAgeGroup}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologyAgeGroup", value)}
      />
      <GovernedFacetSelect
        label="性别"
        options={epidemiologySexOptions}
        value={draft.epidemiologySex}
        state={epidemiologyCatalogState}
        onChange={(value) => update("epidemiologySex", value)}
      />
      <DateRange
        label="统计周期"
        from={draft.epidemiologyPeriodStartFrom}
        to={draft.epidemiologyPeriodEndTo}
        onChange={(from, to) => updateDateRange("epidemiologyPeriodStartFrom", "epidemiologyPeriodEndTo", from, to)}
      />
    </>
  );
}
