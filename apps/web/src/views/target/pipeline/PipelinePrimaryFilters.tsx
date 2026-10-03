import { FacetMultiSelect } from "../../../components/FacetMultiSelect";
import type { PipelineSearchFilters } from "../../../lib/contracts/pipeline";
import type { PipelineSearchResult } from "../../../lib/generated";
import { programModalityLabel } from "../../../lib/programDisplay";
import { TargetPipelineSelect } from "./PipelineFilterControls";
import { developmentPhaseLabel, geographyLabel, isUnavailableFacetOption } from "./presentation";
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
  data: PipelineSearchResult;
  hasUserFilters: boolean;
  onFiltersChange: TargetPipelineProps["onFiltersChange"];
}) {
  const { filters, cachedFacetOptions, updateFilter, setFilters, setComparisonMessage, updateSorting, resetFilters } =
    state;
  return (
    <fieldset className="target-evidence-filters">
      <legend className="sr-only">研发项目筛选</legend>
      <label>
        药物或机构
        <input
          type="search"
          value={filters.query}
          placeholder="输入药物、公司或适应症"
          onChange={(event) => updateFilter("query", event.target.value)}
        />
      </label>
      <FacetMultiSelect
        label="药物类型"
        options={cachedFacetOptions("modality", data.facets?.modality, filters.modalities).map((option) => ({
          ...option,
          label: programModalityLabel(option.value),
        }))}
        selected={filters.modalities}
        onChange={(values) => updateFilter("modalities", values)}
      />
      <FacetMultiSelect
        label="适应症领域"
        options={cachedFacetOptions("therapeutic_area", data.facets?.therapeutic_area, filters.therapeuticAreas)}
        selected={filters.therapeuticAreas}
        onChange={(values) => updateFilter("therapeuticAreas", values)}
      />
      <TargetPipelineSelect
        label="最高阶段"
        value={filters.phase}
        values={data.facets?.phase}
        onChange={(value) => updateFilter("phase", value)}
        formatItem={developmentPhaseLabel}
      />
      <TargetPipelineSelect
        label="地区"
        value={filters.geography}
        values={data.facets?.geography}
        onChange={(value) => updateFilter("geography", value)}
        formatItem={geographyLabel}
      />
      <label>
        项目状态
        <select value={filters.programStatus} onChange={(event) => updateFilter("programStatus", event.target.value)}>
          <option value="">全部</option>
          <option
            value="active"
            disabled={isUnavailableFacetOption(
              data.facets?.program_status?.active ?? 0,
              "active",
              filters.programStatus,
            )}
          >
            在研 ({data.facets?.program_status?.active ?? 0})
          </option>
          <option
            value="inactive"
            disabled={isUnavailableFacetOption(
              data.facets?.program_status?.inactive ?? 0,
              "inactive",
              filters.programStatus,
            )}
          >
            已停止 ({data.facets?.program_status?.inactive ?? 0})
          </option>
          <option
            value="unknown"
            disabled={isUnavailableFacetOption(
              data.facets?.program_status?.unknown ?? 0,
              "unknown",
              filters.programStatus,
            )}
          >
            状态未披露 ({data.facets?.program_status?.unknown ?? 0})
          </option>
        </select>
      </label>
      <label>
        临床结果
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
          <option value="">全部</option>
          <option
            value="true"
            disabled={isUnavailableFacetOption(
              data.facets?.has_clinical_results?.true ?? 0,
              "true",
              filters.hasClinicalResults,
            )}
          >
            已有结果 ({data.facets?.has_clinical_results?.true ?? 0})
          </option>
          <option
            value="false"
            disabled={isUnavailableFacetOption(
              data.facets?.has_clinical_results?.false ?? 0,
              "false",
              filters.hasClinicalResults,
            )}
          >
            暂无结果 ({data.facets?.has_clinical_results?.false ?? 0})
          </option>
        </select>
      </label>
      <label>
        交易信号
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
          <option value="">全部</option>
          <option
            value="true"
            disabled={isUnavailableFacetOption(data.facets?.has_deal?.true ?? 0, "true", filters.hasDeal)}
          >
            已有交易 ({data.facets?.has_deal?.true ?? 0})
          </option>
          <option
            value="false"
            disabled={isUnavailableFacetOption(data.facets?.has_deal?.false ?? 0, "false", filters.hasDeal)}
          >
            暂无交易 ({data.facets?.has_deal?.false ?? 0})
          </option>
        </select>
      </label>
      <label>
        排序方式
        <select
          value={`${filters.sortBy}:${filters.sortDirection}`}
          onChange={(event) => updateSorting(event.target.value)}
        >
          <option value="status_date:desc">最近更新</option>
          <option value="phase:desc">最高阶段优先</option>
          <option value="global_phase:desc">全球阶段优先</option>
          <option value="china_phase:desc">中国阶段优先</option>
          <option value="global_phase_started_at:desc">全球阶段开始日期</option>
          <option value="china_phase_started_at:desc">中国阶段开始日期</option>
          <option value="drug_name:asc">药物名称</option>
          <option value="organization_name:asc">研发机构</option>
          <option value="disease_name:asc">适应症</option>
          <option value="modality:asc">药物类型</option>
          <option value="mechanism_of_action:asc">作用机制</option>
        </select>
      </label>
      <button type="button" onClick={resetFilters} disabled={!hasUserFilters}>
        重置筛选
      </button>
    </fieldset>
  );
}
