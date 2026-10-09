import { CalendarDays, FlaskConical } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { formattingLocale } from "../../lib/i18n";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import { TrialRecordedDate } from "../trials/TrialRecordedDate";
import { clinicalList, clinicalObjectNames } from "./clinicalPresentation";
import { TrialActions } from "./TrialActions";
import { TrialOutcomeSummary } from "./TrialOutcomeSummary";
import { TrialRoleLinks } from "./TrialRoleLinks";
import type { DrugEntityOpener } from "./types";
import { disclosureTypeLabels, lineOfTherapyLabels, trialInitiationLabels, trialResultLabels } from "./vocabulary";

export function DrugClinicalEvidence({
  data,
  onOpen,
  onOpenEntity,
  onOpenTrial,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
  onOpenTrial: (trialId: string) => void;
}) {
  const resultTrials = data.clinical_trials.filter(
    (trial) =>
      trial.has_results ||
      (trial.key_result_count ?? 0) > 0 ||
      trial.outcomes.some((outcome) => (outcome.results ?? []).length),
  );
  if (!data.clinical_trials.length) return <EmptyState title={t("暂无关联临床结果或试验")} />;

  return (
    <div className="drug-clinical-view">
      <section className="drug-profile-section" aria-labelledby="drug-clinical-results-title">
        <header>
          <div>
            <span>{t("报告结果与披露")}</span>
            <h3 id="drug-clinical-results-title">{t("临床结果（{count}）", { count: resultTrials.length })}</h3>
          </div>
          <FlaskConical size={18} aria-hidden="true" />
        </header>
        {resultTrials.length ? (
          <ScrollableTableRegion ariaLabel={t("药物临床结果")} className="drug-clinical-results-region">
            <table aria-label={t("药物临床结果")}>
              <thead>
                <tr>
                  <th>{t("试验")}</th>
                  <th>{t("适应症")}</th>
                  <th>{t("分期与线次")}</th>
                  <th>{t("报告终点")}</th>
                  <th>{t("总体评价")}</th>
                  <th>{t("试验/联用药物")}</th>
                  <th>{t("试验/联用靶点")}</th>
                  <th>{t("最近披露")}</th>
                  <th aria-label={t("操作")} />
                </tr>
              </thead>
              <tbody>
                {resultTrials.map((trial) => (
                  <tr key={trial.id}>
                    <td>
                      <button className="table-link-button" type="button" onClick={() => onOpenTrial(trial.id)}>
                        {trial.registry_id}
                      </button>
                      <small className="cell-subtitle">{trial.acronym ?? trial.official_title}</small>
                    </td>
                    <td>{clinicalList(trial.conditions)}</td>
                    <td>
                      {clinicalList(trial.phases.map(localizedTrialPhase))}
                      <small className="cell-subtitle">
                        {clinicalList(
                          trial.therapy_lines.map((line) => controlledDrugLabel(line, lineOfTherapyLabels)),
                          t("线次未披露"),
                          3,
                        )}
                      </small>
                    </td>
                    <td>
                      <TrialOutcomeSummary trial={trial} />
                    </td>
                    <td>
                      <StatusBadge
                        value={trial.result_evaluation ?? (trial.has_results ? "reported" : "unreported")}
                        label={
                          trial.result_evaluation
                            ? controlledDrugLabel(trial.result_evaluation, trialResultLabels)
                            : trial.has_results
                              ? t("已披露，未评价")
                              : t("未披露")
                        }
                      />
                    </td>
                    <td>
                      <TrialRoleLinks
                        trial={trial}
                        roles={["investigational_drug", "combination_drug"]}
                        onOpenEntity={onOpenEntity}
                      />
                    </td>
                    <td>
                      <TrialRoleLinks
                        trial={trial}
                        roles={["investigational_target", "combination_target"]}
                        onOpenEntity={onOpenEntity}
                      />
                    </td>
                    <td>
                      {trial.latest_result_disclosure ? (
                        <span className="cell-stack">
                          <strong>
                            {controlledDrugLabel(trial.latest_result_disclosure.disclosure_type, disclosureTypeLabels)}
                          </strong>
                          <small>{formatDate(trial.latest_result_disclosure.disclosed_at)}</small>
                          {trial.latest_result_disclosure.conference_name ? (
                            <small>{trial.latest_result_disclosure.conference_name}</small>
                          ) : null}
                        </span>
                      ) : (
                        formatDate(trial.results_first_posted)
                      )}
                    </td>
                    <td>
                      <TrialActions trial={trial} onOpen={onOpen} onOpenTrial={onOpenTrial} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={t("暂无结构化临床结果")} detail={t("关联试验仍保留在下方试验列表")} />
        )}
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-clinical-trials-title">
        <header>
          <div>
            <span>{t("登记与设计")}</span>
            <h3 id="drug-clinical-trials-title">{t("临床试验（{count}）", { count: data.clinical_trials.length })}</h3>
          </div>
          <CalendarDays size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel={t("药物关联临床试验")} className="drug-clinical-trials-region">
          <table aria-label={t("药物关联临床试验")}>
            <thead>
              <tr>
                <th>{t("登记号与标题")}</th>
                <th>{t("状态")}</th>
                <th>{t("研究类型")}</th>
                <th>{t("干预方案")}</th>
                <th>{t("申办方")}</th>
                <th>{t("入组")}</th>
                <th>{t("起止日期")}</th>
                <th aria-label={t("操作")} />
              </tr>
            </thead>
            <tbody>
              {data.clinical_trials.map((trial) => (
                <tr key={trial.id}>
                  <td>
                    <button className="table-link-button" type="button" onClick={() => onOpenTrial(trial.id)}>
                      {trial.registry_id}
                    </button>
                    <small className="cell-subtitle">{trial.official_title}</small>
                  </td>
                  <td>
                    <StatusBadge
                      value={trial.overall_status ?? "UNKNOWN"}
                      label={localizedTrialStatus(trial.overall_status)}
                    />
                  </td>
                  <td>
                    {localizedTrialStudyType(trial.study_type)}
                    <small className="cell-subtitle">
                      {trial.initiation_type
                        ? controlledDrugLabel(trial.initiation_type, trialInitiationLabels)
                        : t("发起类型未披露")}
                    </small>
                  </td>
                  <td>{clinicalObjectNames(trial.interventions, t("未披露"), 3)}</td>
                  <td>{clinicalObjectNames(trial.sponsors)}</td>
                  <td>
                    {trial.enrollment == null ? t("未披露") : trial.enrollment.toLocaleString(formattingLocale())}
                  </td>
                  <td>
                    <span>
                      <TrialRecordedDate value={trial.start_date} precision={trial.start_date_precision} />
                    </span>
                    <small className="cell-subtitle">
                      {t("完成日期")}:{" "}
                      <TrialRecordedDate value={trial.completion_date} precision={trial.completion_date_precision} />
                    </small>
                  </td>
                  <td>
                    <TrialActions trial={trial} onOpen={onOpen} onOpenTrial={onOpenTrial} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>
    </div>
  );
}
