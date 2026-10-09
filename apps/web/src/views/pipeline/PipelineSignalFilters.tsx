import { ChevronDown } from "lucide-react";
import type { PipelineSearchFilters } from "../../lib/contracts/pipeline";
import { pipelineText as t } from "../../lib/i18n/pipeline";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import type { PipelineSignalFilterValues } from "../../lib/pipelineSignals";
import { pipelineResultEvaluationLabels as resultEvaluationLabels } from "../../lib/pipelineSignals";
import { pipelineFilterOptions } from "./filterOptions";
import type { PipelineFilterProps } from "./filterTypes";
export function PipelineSignalFilters({
  filters,
  updateFilter,
  data,
  onSignalsChange,
}: PipelineFilterProps & { onSignalsChange: (changes: Partial<PipelineSignalFilterValues>) => void }) {
  const { resultEvaluations, dealCurrencies } = pipelineFilterOptions(data, filters);
  const signalCount = [
    filters.hasClinicalResults,
    filters.clinicalResultEvaluation,
    filters.hasDeal,
    filters.dealCurrency,
    filters.dealTotalPotentialAmountMin,
    filters.dealTotalPotentialAmountMax,
  ].filter(Boolean).length;
  return (
    <details className="advanced-filter-panel pipeline-advanced-filters" open={signalCount > 0 || undefined}>
      <summary>
        <span>{t("临床结果与交易信号")}</span>
        <small>{signalCount ? t("已选 {count} 项", { count: signalCount }) : t("按需展开")}</small>
        <ChevronDown className="disclosure-chevron" size={16} aria-hidden="true" />
      </summary>
      <div className="pipeline-advanced-grid pipeline-signal-grid">
        <label>
          <span>{t("是否已有临床结果")}</span>
          <select
            value={filters.hasClinicalResults}
            onChange={(event) => {
              const value = event.target.value as PipelineSearchFilters["hasClinicalResults"];
              onSignalsChange({
                hasClinicalResults: value,
                clinicalResultEvaluation: value === "false" ? "" : filters.clinicalResultEvaluation,
              });
            }}
          >
            <option value="">{t("全部")}</option>
            <option value="true">
              {t("有结果")} ({data?.facets?.has_clinical_results?.true ?? 0})
            </option>
            <option value="false">
              {t("无结果")} ({data?.facets?.has_clinical_results?.false ?? 0})
            </option>
          </select>
        </label>
        <label>
          <span>{t("临床结果评价")}</span>
          <select
            value={filters.clinicalResultEvaluation}
            disabled={filters.hasClinicalResults === "false"}
            onChange={(event) => updateFilter("clinicalResultEvaluation", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {resultEvaluations.map((value) => (
              <option value={value} key={value}>
                {professionalEnumLabel(resultEvaluationLabels[value], value)} (
                {data?.facets?.clinical_result_evaluation?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("是否存在交易记录")}</span>
          <select
            value={filters.hasDeal}
            onChange={(event) => {
              const value = event.target.value as PipelineSearchFilters["hasDeal"];
              onSignalsChange({
                hasDeal: value,
                dealCurrency: value === "false" ? "" : filters.dealCurrency,
                dealTotalPotentialAmountMin: value === "false" ? "" : filters.dealTotalPotentialAmountMin,
                dealTotalPotentialAmountMax: value === "false" ? "" : filters.dealTotalPotentialAmountMax,
              });
            }}
          >
            <option value="">{t("全部")}</option>
            <option value="true">
              {t("有交易")} ({data?.facets?.has_deal?.true ?? 0})
            </option>
            <option value="false">
              {t("无交易")} ({data?.facets?.has_deal?.false ?? 0})
            </option>
          </select>
        </label>
        <label>
          <span>{t("交易币种")}</span>
          <select
            value={filters.dealCurrency}
            disabled={filters.hasDeal === "false"}
            onChange={(event) => updateFilter("dealCurrency", event.target.value)}
          >
            <option value="">{t("全部")}</option>
            {dealCurrencies.map((value) => (
              <option value={value} key={value}>
                {value} ({data?.facets?.deal_currency?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>{t("潜在总额下限")}</span>
          <input
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            disabled={filters.hasDeal === "false"}
            value={filters.dealTotalPotentialAmountMin}
            onChange={(event) => updateFilter("dealTotalPotentialAmountMin", event.target.value)}
            placeholder={t("例如 100000000")}
          />
        </label>
        <label>
          <span>{t("潜在总额上限")}</span>
          <input
            type="number"
            min={filters.dealTotalPotentialAmountMin || "0"}
            step="0.01"
            inputMode="decimal"
            disabled={filters.hasDeal === "false"}
            value={filters.dealTotalPotentialAmountMax}
            onChange={(event) => updateFilter("dealTotalPotentialAmountMax", event.target.value)}
            placeholder={t("例如 500000000")}
          />
        </label>
      </div>
    </details>
  );
}
