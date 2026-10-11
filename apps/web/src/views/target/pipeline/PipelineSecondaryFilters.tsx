import { FacetMultiSelect } from "../../../components/FacetMultiSelect";
import type { PipelineSearchFilters } from "../../../lib/contracts/pipeline";
import type { PipelineSearchResult } from "../../../lib/generated";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { TargetPipelineSelect } from "./PipelineFilterControls";
import { geographyLabel, isUnavailableFacetOption, pipelineFacetCount, pipelineFacetCountSuffix } from "./presentation";
import type { TargetPipelineProps } from "./types";
import type { TargetPipelineState } from "./useTargetPipeline";

type SignalChoice = PipelineSearchFilters["hasClinicalResults"];

function SignalSelect({
  label,
  value,
  values,
  onChange,
  positive,
  negative,
}: {
  label: string;
  value: SignalChoice;
  values: Record<string, number> | undefined;
  onChange: (value: SignalChoice) => void;
  positive: string;
  negative: string;
}) {
  const text = useMessages(targetPipelineMessages);
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value as SignalChoice)}>
        <option value="">{text("全部")}</option>
        {(["true", "false"] as const).map((option) => (
          <option
            key={option}
            value={option}
            disabled={isUnavailableFacetOption(pipelineFacetCount(values, option), option, value)}
          >
            {option === "true" ? positive : negative}
            {pipelineFacetCountSuffix(pipelineFacetCount(values, option))}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Secondary controls consume the original query owner and dependent-value rules. */
export function PipelineSecondaryFilters({
  state,
  data,
  onFiltersChange,
}: {
  state: Pick<
    TargetPipelineState,
    "filters" | "cachedFacetOptions" | "updateFilter" | "setFilters" | "setComparisonMessage"
  >;
  data: Pick<PipelineSearchResult, "facets">;
  onFiltersChange: TargetPipelineProps["onFiltersChange"];
}) {
  const text = useMessages(targetPipelineMessages);
  const { filters, cachedFacetOptions, updateFilter, setFilters, setComparisonMessage } = state;
  function updateSignal(field: "hasClinicalResults" | "hasDeal", value: SignalChoice) {
    const nextFilters = { ...filters, [field]: value, offset: 0 };
    if (field === "hasClinicalResults" && value === "false") nextFilters.clinicalResultEvaluation = "";
    if (field === "hasDeal" && value === "false") {
      nextFilters.dealCurrency = "";
      nextFilters.dealTotalPotentialAmountMin = "";
      nextFilters.dealTotalPotentialAmountMax = "";
    }
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
    setComparisonMessage("");
  }
  return (
    <>
      <FacetMultiSelect
        label={text("适应症领域")}
        options={cachedFacetOptions("therapeutic_area", data.facets?.therapeutic_area, filters.therapeuticAreas)}
        selected={filters.therapeuticAreas}
        onChange={(values) => updateFilter("therapeuticAreas", values)}
      />
      <TargetPipelineSelect
        label={text("地区")}
        value={filters.geography}
        values={data.facets?.geography}
        onChange={(value) => updateFilter("geography", value)}
        formatItem={geographyLabel}
      />
      <SignalSelect
        label={text("临床结果")}
        value={filters.hasClinicalResults}
        values={data.facets?.has_clinical_results}
        onChange={(value) => updateSignal("hasClinicalResults", value)}
        positive={text("已有结果")}
        negative={text("暂无结果")}
      />
      <SignalSelect
        label={text("交易信号")}
        value={filters.hasDeal}
        values={data.facets?.has_deal}
        onChange={(value) => updateSignal("hasDeal", value)}
        positive={text("已有交易")}
        negative={text("暂无交易")}
      />
    </>
  );
}
