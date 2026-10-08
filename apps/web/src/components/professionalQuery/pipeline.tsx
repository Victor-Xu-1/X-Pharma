import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { EntityFilterSelect } from "../EntityFilterSelect";
import { DateRange, GovernedFacetField, GovernedFacetSelect } from "./fields";
import { PipelineSignalFields } from "./pipelineSignals";

import { pipelinePhases } from "./presentation";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "pipelineCatalog"
  | "pipelineAdvancedConditionCount"
  | "pipelineSignalConditionCount"
  | "pipelineCatalogState"
  | "modalityOptions"
  | "innovationTypeOptions"
  | "therapeuticAreaOptions"
  | "drugCategoryOptions"
  | "programStatusOptions"
  | "organizationRoleOptions"
  | "organizationTypeOptions"
  | "organizationCountryOptions"
  | "geographyOptions"
  | "developmentRightsOptions"
  | "commercializationRightsOptions"
  | "programTagOptions"
  | "milestoneTypeOptions"
  | "clinicalResultPresenceOptions"
  | "clinicalResultEvaluationOptions"
  | "dealPresenceOptions"
  | "pipelineDealCurrencyOptions"
  | "draft"
  | "setDraft"
  | "setError"
  | "update"
  | "updateDateRange"
>;

export function PipelineFields(props: Props) {
  const {
    pipelineCatalog,
    pipelineAdvancedConditionCount,
    pipelineCatalogState,
    modalityOptions,
    innovationTypeOptions,
    therapeuticAreaOptions,
    drugCategoryOptions,
    programStatusOptions,
    organizationRoleOptions,
    organizationTypeOptions,
    organizationCountryOptions,
    geographyOptions,
    developmentRightsOptions,
    commercializationRightsOptions,
    programTagOptions,
    milestoneTypeOptions,
    draft,
    update,
    updateDateRange,
  } = props;
  return (
    <>
      <div className="professional-entity-row">
        <EntityFilterSelect
          label="药品"
          entityType="drug"
          value={draft.drugEntityId}
          onChange={(value) => update("drugEntityId", value)}
          placeholder="输入规范药品"
        />
        <EntityFilterSelect
          label="靶点"
          entityType="target"
          value={draft.targetEntityId}
          onChange={(value) => update("targetEntityId", value)}
          placeholder="输入规范靶点"
        />
        <EntityFilterSelect
          label="适应症"
          entityType="disease"
          value={draft.diseaseEntityId}
          onChange={(value) => update("diseaseEntityId", value)}
          placeholder="输入疾病或适应症"
        />
        <EntityFilterSelect
          label="研发机构"
          entityType="organization"
          value={draft.organizationEntityId}
          onChange={(value) => update("organizationEntityId", value)}
          placeholder="输入机构名称"
        />
      </div>
      {pipelineCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          正在读取管线筛选选项
        </div>
      ) : null}
      {pipelineCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>管线筛选选项暂不可用</span>
          <button type="button" className="text-button" onClick={() => void pipelineCatalog.refetch()}>
            <RefreshCw size={13} />
            重试
          </button>
        </div>
      ) : null}
      <GovernedFacetField
        label="药物模态"
        options={modalityOptions}
        selected={draft.modalities}
        state={pipelineCatalogState}
        onChange={(values) => update("modalities", values)}
      />
      <GovernedFacetField
        label="创新类型"
        options={innovationTypeOptions}
        selected={draft.pipelineInnovationTypes}
        state={pipelineCatalogState}
        onChange={(values) => update("pipelineInnovationTypes", values)}
      />
      <GovernedFacetField
        label="治疗领域"
        options={therapeuticAreaOptions}
        selected={draft.pipelineTherapeuticAreas}
        state={pipelineCatalogState}
        onChange={(values) => update("pipelineTherapeuticAreas", values)}
      />
      <GovernedFacetField
        label="药品类别"
        options={drugCategoryOptions}
        selected={draft.pipelineDrugCategories}
        state={pipelineCatalogState}
        onChange={(values) => update("pipelineDrugCategories", values)}
      />
      <label>
        <span>总体最高阶段</span>
        <select value={draft.phase} onChange={(event) => update("phase", event.target.value)}>
          <option value="">全部</option>
          {pipelinePhases.map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <GovernedFacetSelect
        label="项目状态"
        options={programStatusOptions}
        value={draft.pipelineProgramStatus}
        state={pipelineCatalogState}
        onChange={(value) => update("pipelineProgramStatus", value)}
      />
      <GovernedFacetSelect
        label="记录地区"
        options={geographyOptions}
        value={draft.geography}
        state={pipelineCatalogState}
        onChange={(value) => update("geography", value)}
      />
      <DateRange
        label="状态日期"
        from={draft.statusDateFrom}
        to={draft.statusDateTo}
        onChange={(from, to) => updateDateRange("statusDateFrom", "statusDateTo", from, to)}
      />
      <details className="professional-more-fields">
        <summary>
          <SlidersHorizontal size={14} />
          <span>更多管线条件</span>
          <small>
            {pipelineAdvancedConditionCount
              ? `已选 ${pipelineAdvancedConditionCount} 项`
              : "区域阶段、机构、权益与里程碑"}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>全球最高阶段</span>
            <select
              value={draft.pipelineGlobalPhase}
              onChange={(event) => update("pipelineGlobalPhase", event.target.value)}
            >
              <option value="">全部</option>
              {pipelinePhases.map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>中国最高阶段</span>
            <select
              value={draft.pipelineChinaPhase}
              onChange={(event) => update("pipelineChinaPhase", event.target.value)}
            >
              <option value="">全部</option>
              {pipelinePhases.map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <DateRange
            label="全球阶段开始日期"
            from={draft.pipelineGlobalPhaseStartedFrom}
            to={draft.pipelineGlobalPhaseStartedTo}
            onChange={(from, to) =>
              updateDateRange("pipelineGlobalPhaseStartedFrom", "pipelineGlobalPhaseStartedTo", from, to)
            }
          />
          <DateRange
            label="中国阶段开始日期"
            from={draft.pipelineChinaPhaseStartedFrom}
            to={draft.pipelineChinaPhaseStartedTo}
            onChange={(from, to) =>
              updateDateRange("pipelineChinaPhaseStartedFrom", "pipelineChinaPhaseStartedTo", from, to)
            }
          />
          <GovernedFacetSelect
            label="研发权益地区"
            options={developmentRightsOptions}
            value={draft.pipelineDevelopmentRightsRegion}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineDevelopmentRightsRegion", value)}
          />
          <GovernedFacetSelect
            label="商业化权益地区"
            options={commercializationRightsOptions}
            value={draft.pipelineCommercializationRightsRegion}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineCommercializationRightsRegion", value)}
          />
          <GovernedFacetSelect
            label="机构角色"
            options={organizationRoleOptions}
            value={draft.pipelineOrganizationRole}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineOrganizationRole", value)}
          />
          <GovernedFacetSelect
            label="机构类型"
            options={organizationTypeOptions}
            value={draft.pipelineOrganizationType}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineOrganizationType", value)}
          />
          <GovernedFacetSelect
            label="机构所在地区"
            options={organizationCountryOptions}
            value={draft.pipelineOrganizationCountryRegion}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineOrganizationCountryRegion", value)}
          />
          <GovernedFacetField
            label="项目标签"
            options={programTagOptions}
            selected={draft.pipelineProgramTags}
            state={pipelineCatalogState}
            onChange={(values) => update("pipelineProgramTags", values)}
          />
          <GovernedFacetSelect
            label="里程碑类型"
            options={milestoneTypeOptions}
            value={draft.pipelineMilestoneType}
            state={pipelineCatalogState}
            onChange={(value) => update("pipelineMilestoneType", value)}
          />
          <DateRange
            label="里程碑日期"
            from={draft.pipelineMilestoneFrom}
            to={draft.pipelineMilestoneTo}
            onChange={(from, to) => updateDateRange("pipelineMilestoneFrom", "pipelineMilestoneTo", from, to)}
          />
        </div>
      </details>
      <PipelineSignalFields {...props} />
    </>
  );
}
