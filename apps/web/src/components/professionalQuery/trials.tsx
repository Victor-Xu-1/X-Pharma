import { FileBadge, SlidersHorizontal } from "lucide-react";
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
  return (
    <>
      <label>
        <span>注册平台</span>
        <select value={draft.registry} onChange={(event) => update("registry", event.target.value)}>
          <option value="">全部</option>
          <option value="ClinicalTrials.gov">ClinicalTrials.gov</option>
          <option value="ChiCTR">ChiCTR</option>
          <option value="EU CTIS">EU CTIS</option>
        </select>
      </label>
      <label>
        <span>招募状态</span>
        <select value={draft.trialStatus} onChange={(event) => update("trialStatus", event.target.value)}>
          <option value="">全部</option>
          <option value="RECRUITING">招募中</option>
          <option value="ACTIVE_NOT_RECRUITING">进行中，停止招募</option>
          <option value="COMPLETED">已完成</option>
          <option value="TERMINATED">终止</option>
        </select>
      </label>
      <label>
        <span>临床分期</span>
        <select value={draft.trialPhase} onChange={(event) => update("trialPhase", event.target.value)}>
          <option value="">全部</option>
          {trialPhases.map(([value, label]) => (
            <option value={value} key={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>研究类型</span>
        <select value={draft.studyType} onChange={(event) => update("studyType", event.target.value)}>
          <option value="">全部</option>
          <option value="INTERVENTIONAL">干预性研究</option>
          <option value="OBSERVATIONAL">观察性研究</option>
          <option value="EXPANDED_ACCESS">扩大使用</option>
        </select>
      </label>
      <label>
        <span>结果发布</span>
        <select
          aria-label="结果发布"
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
          <option value="">全部</option>
          <option value="true">已发布</option>
          <option value="false">未发布</option>
        </select>
      </label>
      <DateRange
        label="结果发布日期"
        from={draft.trialResultsPostedFrom}
        to={draft.trialResultsPostedTo}
        onChange={(from, to) => updateDateRange("trialResultsPostedFrom", "trialResultsPostedTo", from, to)}
      />
      <details className="professional-more-fields" open={trialProfileConditionCount > 0 || undefined}>
        <summary>
          <SlidersHorizontal size={14} />
          <span>试验属性与结果评价</span>
          <small>{trialProfileConditionCount ? `已选 ${trialProfileConditionCount} 项` : "按需展开"}</small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>试验简称</span>
            <input
              value={draft.trialAcronym}
              onChange={(event) => update("trialAcronym", event.target.value)}
              placeholder="如 KEYNOTE、CheckMate"
              maxLength={240}
            />
          </label>
          <label>
            <span>发起类型</span>
            <select
              value={draft.trialInitiationType}
              onChange={(event) => update("trialInitiationType", event.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(trialInitiationTypeLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>治疗线次</span>
            <select value={draft.trialTherapyLine} onChange={(event) => update("trialTherapyLine", event.target.value)}>
              <option value="">全部</option>
              {Object.entries(trialTherapyLineLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>结果最优评价</span>
            <select
              value={draft.trialResultEvaluation}
              disabled={draft.trialHasResults === "false"}
              onChange={(event) => update("trialResultEvaluation", event.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(trialResultEvaluationLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>
      <details className="professional-more-fields" open={trialEvidenceConditionCount > 0 || undefined}>
        <summary>
          <FileBadge size={14} />
          <span>关键结果与发表证据</span>
          <small>{trialEvidenceConditionCount ? `已选 ${trialEvidenceConditionCount} 项` : "按需展开"}</small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>关键结果</span>
            <select
              value={draft.trialHasKeyResult}
              onChange={(event) => update("trialHasKeyResult", event.target.value)}
            >
              <option value="">全部</option>
              {Object.entries(trialKeyResultLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>发表编号</span>
            <input
              value={draft.trialPublicationId}
              onChange={(event) => update("trialPublicationId", event.target.value)}
              placeholder="PMID、DOI 或会议摘要编号"
              maxLength={240}
            />
          </label>
          <label>
            <span>会议</span>
            <input
              value={draft.trialConference}
              onChange={(event) => update("trialConference", event.target.value)}
              placeholder="如 ASCO、AACR"
              maxLength={500}
            />
          </label>
          <DateRange
            label="结果披露日期"
            from={draft.trialDisclosedFrom}
            to={draft.trialDisclosedTo}
            onChange={(from, to) => updateDateRange("trialDisclosedFrom", "trialDisclosedTo", from, to)}
          />
        </div>
      </details>
    </>
  );
}
