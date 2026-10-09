import type { CompetitiveProgramRead } from "../../lib/generated";
import { pipelineText as t } from "../../lib/i18n/pipeline";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { pipelineResultEvaluationLabels as resultEvaluationLabels } from "../../lib/pipelineSignals";
export function ProgramClinicalSignals({
  program,
  onOpen,
}: {
  program: CompetitiveProgramRead;
  onOpen: (id: string) => void;
}) {
  return (
    <span className="table-stacked-copy">
      {(program.clinical_trial_count ?? 0) > 0 ? (
        <button
          className="table-link-button"
          type="button"
          aria-label={t("查看 {name} 的 {count} 项临床试验", {
            name: program.drug_name,
            count: program.clinical_trial_count ?? 0,
          })}
          onClick={() => onOpen(program.drug_entity_id)}
        >
          {t("{count} 项试验", { count: program.clinical_trial_count ?? 0 })}
        </button>
      ) : (
        <span>{t("{count} 项试验", { count: 0 })}</span>
      )}
      <small>
        {program.has_clinical_results
          ? (program.clinical_result_evaluations ?? [])
              .map((value) =>
                resultEvaluationLabels[value] ? professionalEnumLabel(resultEvaluationLabels[value], value) : value,
              )
              .join("、") || t("已有结果")
          : t("未观察到结果")}
      </small>
    </span>
  );
}

export function ProgramDealSignals({
  program,
  onOpen,
}: {
  program: CompetitiveProgramRead;
  onOpen: (id: string) => void;
}) {
  return (
    <span className="table-stacked-copy">
      {(program.deal_count ?? 0) > 0 ? (
        <button
          className="table-link-button"
          type="button"
          aria-label={t("查看 {name} 的 {count} 笔交易", {
            name: program.drug_name,
            count: program.deal_count ?? 0,
          })}
          onClick={() => onOpen(program.drug_entity_id)}
        >
          {t("{count} 笔交易", { count: program.deal_count ?? 0 })}
        </button>
      ) : (
        <span>{t("{count} 笔交易", { count: 0 })}</span>
      )}
      <small>{program.deal_currencies?.join("、") || t("未披露币种")}</small>
    </span>
  );
}

export function ProgramRights({ program }: { program: CompetitiveProgramRead }) {
  return (
    <span className="table-stacked-copy">
      <span>{t("研发：{regions}", { regions: program.development_rights_regions?.join("、") || t("未披露") })}</span>
      <small>
        {t("商业化：{regions}", {
          regions: program.commercialization_rights_regions?.join("、") || t("未披露"),
        })}
      </small>
    </span>
  );
}
