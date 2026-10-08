import { SlidersHorizontal } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import type { ProfessionalSearchDraft } from "../../lib/professionalSearch";
import { GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "pipelineSignalConditionCount"
  | "clinicalResultPresenceOptions"
  | "clinicalResultEvaluationOptions"
  | "dealPresenceOptions"
  | "pipelineDealCurrencyOptions"
  | "draft"
  | "setDraft"
  | "setError"
  | "update"
  | "pipelineCatalogState"
>;

export function PipelineSignalFields({
  pipelineSignalConditionCount,
  clinicalResultPresenceOptions,
  clinicalResultEvaluationOptions,
  dealPresenceOptions,
  pipelineDealCurrencyOptions,
  draft,
  setDraft,
  setError,
  update,
  pipelineCatalogState,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <details className="professional-more-fields" open={pipelineSignalConditionCount > 0 || undefined}>
      <summary>
        <SlidersHorizontal size={14} />
        <span>{t("临床结果与交易信号")}</span>
        <small>
          {pipelineSignalConditionCount ? t("已选 {count} 项", { count: pipelineSignalConditionCount }) : t("按需展开")}
        </small>
      </summary>
      <div className="professional-more-fields-grid">
        <GovernedFacetSelect
          label={t("是否已有临床结果")}
          options={clinicalResultPresenceOptions}
          value={draft.pipelineHasClinicalResults}
          state={pipelineCatalogState}
          onChange={(value) => {
            const next = value as ProfessionalSearchDraft["pipelineHasClinicalResults"];
            setDraft((current) => ({
              ...current,
              pipelineHasClinicalResults: next,
              pipelineClinicalResultEvaluation: next === "false" ? "" : current.pipelineClinicalResultEvaluation,
            }));
            setError("");
          }}
        />
        <GovernedFacetSelect
          label={t("临床结果评价")}
          options={clinicalResultEvaluationOptions}
          value={draft.pipelineClinicalResultEvaluation}
          state={pipelineCatalogState}
          disabled={draft.pipelineHasClinicalResults === "false"}
          onChange={(value) => update("pipelineClinicalResultEvaluation", value)}
        />
        <GovernedFacetSelect
          label={t("是否存在交易记录")}
          options={dealPresenceOptions}
          value={draft.pipelineHasDeal}
          state={pipelineCatalogState}
          onChange={(value) => {
            const next = value as ProfessionalSearchDraft["pipelineHasDeal"];
            setDraft((current) => ({
              ...current,
              pipelineHasDeal: next,
              pipelineDealCurrency: next === "false" ? "" : current.pipelineDealCurrency,
              pipelineDealTotalPotentialAmountMin: next === "false" ? "" : current.pipelineDealTotalPotentialAmountMin,
              pipelineDealTotalPotentialAmountMax: next === "false" ? "" : current.pipelineDealTotalPotentialAmountMax,
            }));
            setError("");
          }}
        />
        <GovernedFacetSelect
          label={t("交易币种")}
          options={pipelineDealCurrencyOptions}
          value={draft.pipelineDealCurrency}
          state={pipelineCatalogState}
          disabled={draft.pipelineHasDeal === "false"}
          onChange={(value) => update("pipelineDealCurrency", value)}
        />
        <label>
          <span>{t("潜在总额下限")}</span>
          <input
            type="number"
            min="0"
            step="0.01"
            inputMode="decimal"
            disabled={draft.pipelineHasDeal === "false"}
            value={draft.pipelineDealTotalPotentialAmountMin}
            onChange={(event) => update("pipelineDealTotalPotentialAmountMin", event.target.value)}
            placeholder={t("例如 100000000")}
          />
        </label>
        <label>
          <span>{t("潜在总额上限")}</span>
          <input
            type="number"
            min={draft.pipelineDealTotalPotentialAmountMin || "0"}
            step="0.01"
            inputMode="decimal"
            disabled={draft.pipelineHasDeal === "false"}
            value={draft.pipelineDealTotalPotentialAmountMax}
            onChange={(event) => update("pipelineDealTotalPotentialAmountMax", event.target.value)}
            placeholder={t("例如 500000000")}
          />
        </label>
      </div>
    </details>
  );
}
