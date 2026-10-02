import { EntityFilterSelect } from "../../../components/EntityFilterSelect";
import { FacetMultiSelect } from "../../../components/FacetMultiSelect";
import type { PipelineSearchResult } from "../../../lib/generated";
import { pipelineResultEvaluationLabels } from "../../../lib/pipelineSignals";
import { TargetPipelineDateRange, TargetPipelineSelect } from "./PipelineFilterControls";
import { developmentPhaseLabel, organizationRoleLabel } from "./presentation";
import type { TargetPipelineState } from "./useTargetPipeline";

export function PipelineAdvancedFilters({
  state,
  data,
  advancedFilterCount,
  programTagOptions,
}: {
  state: Pick<
    TargetPipelineState,
    "filters" | "cachedFacetOptions" | "updateFilter" | "advancedFiltersOpen" | "setAdvancedFiltersOpen"
  >;
  data: PipelineSearchResult;
  advancedFilterCount: number;
  programTagOptions: ReturnType<TargetPipelineState["cachedFacetOptions"]>;
}) {
  const { filters, cachedFacetOptions, updateFilter, advancedFiltersOpen, setAdvancedFiltersOpen } = state;
  return (
    <details
      className="advanced-filter-panel pipeline-advanced-filters"
      open={advancedFiltersOpen}
      onToggle={(event) => setAdvancedFiltersOpen(event.currentTarget.open)}
    >
      <summary>
        <span>更多筛选</span>
        <span>{advancedFilterCount ? `已选 ${advancedFilterCount} 项` : "创新、机构、区域阶段与时间"}</span>
      </summary>
      <div className="pipeline-advanced-grid">
        <FacetMultiSelect
          label="创新类型"
          options={cachedFacetOptions("innovation_type", data.facets?.innovation_type, filters.innovationTypes)}
          selected={filters.innovationTypes}
          onChange={(values) => updateFilter("innovationTypes", values)}
        />
        <FacetMultiSelect
          label="药品类别"
          options={cachedFacetOptions("drug_category", data.facets?.drug_category, filters.drugCategories)}
          selected={filters.drugCategories}
          onChange={(values) => updateFilter("drugCategories", values)}
        />
        <TargetPipelineSelect
          label="机构角色"
          value={filters.organizationRole}
          values={data.facets?.organization_role}
          onChange={(value) => updateFilter("organizationRole", value)}
          formatItem={organizationRoleLabel}
        />
        <EntityFilterSelect
          label="研发机构"
          entityType="organization"
          value={filters.organizationEntityId}
          onChange={(value) => updateFilter("organizationEntityId", value)}
          placeholder="输入至少 2 个字符查找机构"
        />
        <TargetPipelineSelect
          label="机构标签"
          value={filters.organizationType}
          values={data.facets?.organization_type}
          onChange={(value) => updateFilter("organizationType", value)}
        />
        <TargetPipelineSelect
          label="机构所在地区"
          value={filters.organizationCountryRegion}
          values={data.facets?.organization_country_region}
          onChange={(value) => updateFilter("organizationCountryRegion", value)}
        />
        <TargetPipelineSelect
          label="全球最高阶段"
          value={filters.globalPhase}
          values={data.facets?.global_phase}
          onChange={(value) => updateFilter("globalPhase", value)}
          formatItem={developmentPhaseLabel}
        />
        <TargetPipelineSelect
          label="中国最高阶段"
          value={filters.chinaPhase}
          values={data.facets?.china_phase}
          onChange={(value) => updateFilter("chinaPhase", value)}
          formatItem={developmentPhaseLabel}
        />
        <TargetPipelineSelect
          label="研发权益地区"
          value={filters.developmentRightsRegion}
          values={data.facets?.development_rights_region}
          onChange={(value) => updateFilter("developmentRightsRegion", value)}
        />
        <TargetPipelineSelect
          label="商业化权益地区"
          value={filters.commercializationRightsRegion}
          values={data.facets?.commercialization_rights_region}
          onChange={(value) => updateFilter("commercializationRightsRegion", value)}
        />
        {programTagOptions.length || filters.programTags.length ? (
          <FacetMultiSelect
            label="项目标签"
            options={programTagOptions}
            selected={filters.programTags}
            onChange={(values) => updateFilter("programTags", values)}
          />
        ) : null}
        <TargetPipelineSelect
          label="里程碑类型"
          value={filters.milestoneType}
          values={data.facets?.milestone_type}
          onChange={(value) => updateFilter("milestoneType", value)}
        />
        <TargetPipelineSelect
          label="临床结果评价"
          value={filters.clinicalResultEvaluation}
          values={data.facets?.clinical_result_evaluation}
          onChange={(value) => updateFilter("clinicalResultEvaluation", value)}
          formatItem={(value) => pipelineResultEvaluationLabels[value] ?? value}
          disabled={filters.hasClinicalResults === "false"}
        />
        <TargetPipelineSelect
          label="交易币种"
          value={filters.dealCurrency}
          values={data.facets?.deal_currency}
          onChange={(value) => updateFilter("dealCurrency", value)}
          disabled={filters.hasDeal === "false"}
        />
        <label>
          潜在交易总额下限
          <input
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            disabled={filters.hasDeal === "false"}
            value={filters.dealTotalPotentialAmountMin}
            onChange={(event) => updateFilter("dealTotalPotentialAmountMin", event.target.value)}
            placeholder="例如 100000000"
          />
        </label>
        <label>
          潜在交易总额上限
          <input
            type="number"
            min={filters.dealTotalPotentialAmountMin || "0"}
            step="0.01"
            inputMode="decimal"
            disabled={filters.hasDeal === "false"}
            value={filters.dealTotalPotentialAmountMax}
            onChange={(event) => updateFilter("dealTotalPotentialAmountMax", event.target.value)}
            placeholder="例如 500000000"
          />
        </label>
        <TargetPipelineDateRange
          legend="全球阶段开始日期"
          from={filters.globalPhaseStartedFrom}
          to={filters.globalPhaseStartedTo}
          onFromChange={(value) => updateFilter("globalPhaseStartedFrom", value)}
          onToChange={(value) => updateFilter("globalPhaseStartedTo", value)}
        />
        <TargetPipelineDateRange
          legend="中国阶段开始日期"
          from={filters.chinaPhaseStartedFrom}
          to={filters.chinaPhaseStartedTo}
          onFromChange={(value) => updateFilter("chinaPhaseStartedFrom", value)}
          onToChange={(value) => updateFilter("chinaPhaseStartedTo", value)}
        />
        <TargetPipelineDateRange
          legend="状态更新日期"
          from={filters.statusDateFrom}
          to={filters.statusDateTo}
          onFromChange={(value) => updateFilter("statusDateFrom", value)}
          onToChange={(value) => updateFilter("statusDateTo", value)}
        />
        <TargetPipelineDateRange
          legend="里程碑日期"
          from={filters.milestoneFrom}
          to={filters.milestoneTo}
          onFromChange={(value) => updateFilter("milestoneFrom", value)}
          onToChange={(value) => updateFilter("milestoneTo", value)}
        />
      </div>
    </details>
  );
}
