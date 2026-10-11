import { FacetMultiSelect } from "../../../components/FacetMultiSelect";
import type { PipelineSearchFilters } from "../../../lib/contracts/pipeline";
import type { PipelineSearchResult } from "../../../lib/generated";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { programModalityLabel } from "../../../lib/programDisplay";
import { TargetPipelineSelect } from "./PipelineFilterControls";
import {
  developmentPhaseLabel,
  geographyLabel,
  isUnavailableFacetOption,
  pipelineFacetCount,
  pipelineFacetCountSuffix,
} from "./presentation";
import type { TargetPipelineProps } from "./types";
import type { TargetPipelineState } from "./useTargetPipeline";

export function PipelinePrimaryFilters({
  state,
  data,
  hasUserFilters,
  onFiltersChange,
}: {
  state: Pick<
    TargetPipelineState,
    | "filters"
    | "cachedFacetOptions"
    | "updateFilter"
    | "setFilters"
    | "setComparisonMessage"
    | "updateSorting"
    | "resetFilters"
  >;
  data: Pick<PipelineSearchResult, "facets">;
  hasUserFilters: boolean;
  onFiltersChange: TargetPipelineProps["onFiltersChange"];
}) {
  const text = useMessages(targetPipelineMessages);
  const { filters, cachedFacetOptions, updateFilter, setFilters, setComparisonMessage, updateSorting, resetFilters } =
    state;
  return (
    <fieldset className="target-evidence-filters">
      <legend className="sr-only">{text("研发项目筛选")}</legend>
      <label>
        {text("药物或机构")}
        <input
          type="search"
          value={filters.query}
          placeholder={text("输入药物、公司或适应症")}
          onChange={(event) => updateFilter("query", event.target.value)}
        />
      </label>
      <FacetMultiSelect
        label={text("药物类型")}
        options={cachedFacetOptions("modality", data.facets?.modality, filters.modalities).map((option) => ({
          ...option,
          label: programModalityLabel(option.value),
        }))}
        selected={filters.modalities}
        onChange={(values) => updateFilter("modalities", values)}
      />
      <FacetMultiSelect
        label={text("适应症领域")}
        options={cachedFacetOptions("therapeutic_area", data.facets?.therapeutic_area, filters.therapeuticAreas)}
        selected={filters.therapeuticAreas}
        onChange={(values) => updateFilter("therapeuticAreas", values)}
      />
      <TargetPipelineSelect
        label={text("最高阶段")}
        value={filters.phase}
        values={data.facets?.phase}
        onChange={(value) => updateFilter("phase", value)}
        formatItem={developmentPhaseLabel}
      />
      <TargetPipelineSelect
        label={text("地区")}
        value={filters.geography}
        values={data.facets?.geography}
        onChange={(value) => updateFilter("geography", value)}
        formatItem={geographyLabel}
      />
      <label>
        {text("项目状态")}
        <select value={filters.programStatus} onChange={(event) => updateFilter("programStatus", event.target.value)}>
          <option value="">{text("全部")}</option>
          <option
            value="active"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.program_status, "active"),
              "active",
              filters.programStatus,
            )}
          >
            {text("在研")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.program_status, "active"))}
          </option>
          <option
            value="inactive"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.program_status, "inactive"),
              "inactive",
              filters.programStatus,
            )}
          >
            {text("已停止")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.program_status, "inactive"))}
          </option>
          <option
            value="unknown"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.program_status, "unknown"),
              "unknown",
              filters.programStatus,
            )}
          >
            {text("状态未披露")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.program_status, "unknown"))}
          </option>
        </select>
      </label>
      <label>
        {text("临床结果")}
        <select
          value={filters.hasClinicalResults}
          onChange={(event) => {
            const value = event.target.value as PipelineSearchFilters["hasClinicalResults"];
            const nextFilters = {
              ...filters,
              hasClinicalResults: value,
              clinicalResultEvaluation: value === "false" ? "" : filters.clinicalResultEvaluation,
              offset: 0,
            };
            setFilters(nextFilters);
            onFiltersChange?.(nextFilters);
            setComparisonMessage("");
          }}
        >
          <option value="">{text("全部")}</option>
          <option
            value="true"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.has_clinical_results, "true"),
              "true",
              filters.hasClinicalResults,
            )}
          >
            {text("已有结果")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.has_clinical_results, "true"))}
          </option>
          <option
            value="false"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.has_clinical_results, "false"),
              "false",
              filters.hasClinicalResults,
            )}
          >
            {text("暂无结果")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.has_clinical_results, "false"))}
          </option>
        </select>
      </label>
      <label>
        {text("交易信号")}
        <select
          value={filters.hasDeal}
          onChange={(event) => {
            const value = event.target.value as PipelineSearchFilters["hasDeal"];
            const nextFilters = {
              ...filters,
              hasDeal: value,
              dealCurrency: value === "false" ? "" : filters.dealCurrency,
              dealTotalPotentialAmountMin: value === "false" ? "" : filters.dealTotalPotentialAmountMin,
              dealTotalPotentialAmountMax: value === "false" ? "" : filters.dealTotalPotentialAmountMax,
              offset: 0,
            };
            setFilters(nextFilters);
            onFiltersChange?.(nextFilters);
            setComparisonMessage("");
          }}
        >
          <option value="">{text("全部")}</option>
          <option
            value="true"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.has_deal, "true"),
              "true",
              filters.hasDeal,
            )}
          >
            {text("已有交易")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.has_deal, "true"))}
          </option>
          <option
            value="false"
            disabled={isUnavailableFacetOption(
              pipelineFacetCount(data.facets?.has_deal, "false"),
              "false",
              filters.hasDeal,
            )}
          >
            {text("暂无交易")}
            {pipelineFacetCountSuffix(pipelineFacetCount(data.facets?.has_deal, "false"))}
          </option>
        </select>
      </label>
      <label>
        {text("排序方式")}
        <select
          value={`${filters.sortBy}:${filters.sortDirection}`}
          onChange={(event) => updateSorting(event.target.value)}
        >
          <option value="status_date:desc">{text("最近更新")}</option>
          <option value="phase:desc">{text("最高阶段优先")}</option>
          <option value="global_phase:desc">{text("全球阶段优先")}</option>
          <option value="china_phase:desc">{text("中国阶段优先")}</option>
          <option value="global_phase_started_at:desc">{text("全球阶段开始日期")}</option>
          <option value="china_phase_started_at:desc">{text("中国阶段开始日期")}</option>
          <option value="drug_name:asc">{text("药物名称")}</option>
          <option value="organization_name:asc">{text("研发机构")}</option>
          <option value="disease_name:asc">{text("适应症")}</option>
          <option value="modality:asc">{text("药物类型")}</option>
          <option value="mechanism_of_action:asc">{text("作用机制")}</option>
        </select>
      </label>
      <button type="button" onClick={resetFilters} disabled={!hasUserFilters}>
        {text("重置筛选")}
      </button>
    </fieldset>
  );
}
