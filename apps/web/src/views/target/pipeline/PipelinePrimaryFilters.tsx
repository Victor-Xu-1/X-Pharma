import { FacetMultiSelect } from "../../../components/FacetMultiSelect";
import type { PipelineSearchResult } from "../../../lib/generated";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { programModalityLabel } from "../../../lib/programDisplay";
import { TargetPipelineSelect } from "./PipelineFilterControls";
import {
  developmentPhaseLabel,
  isUnavailableFacetOption,
  pipelineFacetCount,
  pipelineFacetCountSuffix,
} from "./presentation";
import type { TargetPipelineState } from "./useTargetPipeline";
import "./PipelinePrimaryFilters.css";

export function PipelinePrimaryFilters({
  state,
  data,
  hasUserFilters,
}: {
  state: Pick<
    TargetPipelineState,
    "filters" | "cachedFacetOptions" | "updateFilter" | "updateSorting" | "resetFilters"
  >;
  data: Pick<PipelineSearchResult, "facets">;
  hasUserFilters: boolean;
}) {
  const text = useMessages(targetPipelineMessages);
  const { filters, cachedFacetOptions, updateFilter, updateSorting, resetFilters } = state;
  return (
    <fieldset className="target-evidence-filters target-pipeline-primary-filters">
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
      <TargetPipelineSelect
        label={text("最高阶段")}
        value={filters.phase}
        values={data.facets?.phase}
        onChange={(value) => updateFilter("phase", value)}
        formatItem={developmentPhaseLabel}
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
      <button type="button" className="secondary-button" onClick={resetFilters} disabled={!hasUserFilters}>
        {text("重置筛选")}
      </button>
    </fieldset>
  );
}
