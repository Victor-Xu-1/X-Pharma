import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import type { DrugClinicalTrial } from "./types";

export function TrialOutcomeSummary({ trial }: { trial: DrugClinicalTrial }) {
  const reported = trial.outcomes.filter((outcome) => (outcome.results ?? []).length);
  if (!reported.length) {
    return <span>{trial.has_results ? t("结果已发布，结构化终点未披露") : t("未发布结果")}</span>;
  }
  const outcomes = [...reported].sort((left, right) => {
    const leftPrimary = left.outcome_type?.toUpperCase() === "PRIMARY" ? 0 : 1;
    const rightPrimary = right.outcome_type?.toUpperCase() === "PRIMARY" ? 0 : 1;
    return leftPrimary - rightPrimary;
  });
  return (
    <div className="drug-clinical-outcomes">
      {sourceRecordRows(outcomes.slice(0, 2)).map(({ value: outcome, key }) => (
        <span key={key}>
          <strong>{outcome.measure}</strong>
          <small>
            {(outcome.results ?? [])
              .slice(0, 2)
              .map((result) => `${result.group_label}: ${result.value}${result.unit ? ` ${result.unit}` : ""}`)
              .join(t("；"))}
          </small>
          {outcome.time_frame ? <small>{outcome.time_frame}</small> : null}
        </span>
      ))}
      {outcomes.length > 2 ? <small>{t("另有 {count} 项结构化终点", { count: outcomes.length - 2 })}</small> : null}
      {outcomes.length > 2 || outcomes.some((outcome) => (outcome.results?.length ?? 0) > 2) ? (
        <details className="program-history">
          <summary>{t("全部已报告终点与结果组")}</summary>
          {sourceRecordRows(outcomes).map(({ value: outcome, key }) => (
            <div key={key}>
              <strong>{outcome.measure}</strong>
              {sourceRecordRows(outcome.results ?? []).map(({ value: result, key }) => (
                <small key={key}>
                  {`${result.group_label}: ${result.value}${result.unit ? ` ${result.unit}` : ""}`}
                </small>
              ))}
              {outcome.time_frame ? <small>{outcome.time_frame}</small> : null}
            </div>
          ))}
        </details>
      ) : null}
    </div>
  );
}
