import { FileBadge, SlidersHorizontal } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import {
  trialInitiationTypeLabels,
  trialKeyResultLabels,
  trialResultEvaluationLabels,
  trialTherapyLineLabels,
} from "../../lib/trialFilters";
import { DateRange } from "./fields";

import { trialPhases } from "./presentation";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "trialProfileConditionCount"
  | "trialEvidenceConditionCount"
  | "draft"
  | "setDraft"
  | "setError"
  | "update"
  | "updateDateRange"
>;

export function TrialsFields({
  trialProfileConditionCount,
  trialEvidenceConditionCount,
  draft,
  setDraft,
  setError,
  update,
  updateDateRange,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      <label>
        <span>{t("注册平台")}</span>
        <select
          aria-label={t("注册平台")}
          value={draft.registry}
          onChange={(event) => update("registry", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          <option value="ClinicalTrials.gov">ClinicalTrials.gov</option>
          <option value="ChiCTR">ChiCTR</option>
          <option value="EU CTIS">EU CTIS</option>
        </select>
      </label>
      <label>
        <span>{t("招募状态")}</span>
        <select
          aria-label={t("招募状态")}
          value={draft.trialStatus}
          onChange={(event) => update("trialStatus", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          <option value="RECRUITING">{t("招募中")}</option>
          <option value="ACTIVE_NOT_RECRUITING">{t("进行中，停止招募")}</option>
          <option value="COMPLETED">{t("已完成")}</option>
          <option value="TERMINATED">{t("终止")}</option>
        </select>
      </label>
      <label>
        <span>{t("临床分期")}</span>
        <select
          aria-label={t("临床分期")}
          value={draft.trialPhase}
          onChange={(event) => update("trialPhase", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {trialPhases.map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("研究类型")}</span>
        <select
          aria-label={t("研究类型")}
          value={draft.studyType}
          onChange={(event) => update("studyType", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          <option value="INTERVENTIONAL">{t("干预性研究")}</option>
          <option value="OBSERVATIONAL">{t("观察性研究")}</option>
          <option value="EXPANDED_ACCESS">{t("扩大使用")}</option>
        </select>
      </label>
      <label>
        <span>{t("结果发布")}</span>
        <select
          aria-label={t("结果发布")}
          value={draft.trialHasResults}
          onChange={(event) => {
            const value = event.target.value;
            setDraft((current) => ({
              ...current,
              trialHasResults: value,
              trialResultEvaluation: value === "false" ? "" : current.trialResultEvaluation,
            }));
            setError("");
          }}
        >
          <option value="">{t("全部")}</option>
          <option value="true">{t("已发布")}</option>
          <option value="false">{t("未发布")}</option>
        </select>
      </label>
      <DateRange
        label={t("结果发布日期")}
        from={draft.trialResultsPostedFrom}
        to={draft.trialResultsPostedTo}
        onChange={(from, to) => updateDateRange("trialResultsPostedFrom", "trialResultsPostedTo", from, to)}
      />
      <details className="professional-more-fields" open={trialProfileConditionCount > 0 || undefined}>
        <summary>
          <SlidersHorizontal size={14} />
          <span>{t("试验属性与结果评价")}</span>
          <small>
            {trialProfileConditionCount ? t("已选 {count} 项", { count: trialProfileConditionCount }) : t("按需展开")}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>{t("试验简称")}</span>
            <input
              value={draft.trialAcronym}
              onChange={(event) => update("trialAcronym", event.target.value)}
              placeholder={t("如 KEYNOTE、CheckMate")}
              maxLength={240}
            />
          </label>
          <label>
            <span>{t("发起类型")}</span>
            <select
              value={draft.trialInitiationType}
              aria-label={t("发起类型")}
              onChange={(event) => update("trialInitiationType", event.target.value)}
            >
              <option value="">{t("全部")}</option>
              {Object.entries(trialInitiationTypeLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {professionalEnumLabel(label, value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("治疗线次")}</span>
            <select
              aria-label={t("治疗线次")}
              value={draft.trialTherapyLine}
              onChange={(event) => update("trialTherapyLine", event.target.value)}
            >
              <option value="">{t("全部")}</option>
              {Object.entries(trialTherapyLineLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {professionalEnumLabel(label, value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("结果最优评价")}</span>
            <select
              value={draft.trialResultEvaluation}
              aria-label={t("结果最优评价")}
              disabled={draft.trialHasResults === "false"}
              onChange={(event) => update("trialResultEvaluation", event.target.value)}
            >
              <option value="">{t("全部")}</option>
              {Object.entries(trialResultEvaluationLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {professionalEnumLabel(label, value)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>
      <details className="professional-more-fields" open={trialEvidenceConditionCount > 0 || undefined}>
        <summary>
          <FileBadge size={14} />
          <span>{t("关键结果与发表证据")}</span>
          <small>
            {trialEvidenceConditionCount ? t("已选 {count} 项", { count: trialEvidenceConditionCount }) : t("按需展开")}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>{t("关键结果")}</span>
            <select
              value={draft.trialHasKeyResult}
              aria-label={t("关键结果")}
              onChange={(event) => update("trialHasKeyResult", event.target.value)}
            >
              <option value="">{t("全部")}</option>
              {Object.entries(trialKeyResultLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {professionalEnumLabel(label, value)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t("发表编号")}</span>
            <input
              value={draft.trialPublicationId}
              onChange={(event) => update("trialPublicationId", event.target.value)}
              placeholder={t("PMID、DOI 或会议摘要编号")}
              maxLength={240}
            />
          </label>
          <label>
            <span>{t("会议")}</span>
            <input
              value={draft.trialConference}
              onChange={(event) => update("trialConference", event.target.value)}
              placeholder={t("如 ASCO、AACR")}
              maxLength={500}
            />
          </label>
          <DateRange
            label={t("结果披露日期")}
            from={draft.trialDisclosedFrom}
            to={draft.trialDisclosedTo}
            onChange={(from, to) => updateDateRange("trialDisclosedFrom", "trialDisclosedTo", from, to)}
          />
        </div>
      </details>
    </>
  );
}
