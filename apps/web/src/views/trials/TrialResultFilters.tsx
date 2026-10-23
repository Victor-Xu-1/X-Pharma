import { SecondaryFilters } from "../../components/SecondaryFilters";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import {
  trialKeyResultLabels as keyResultLabels,
  trialResultEvaluationLabels as resultEvaluationLabels,
} from "../../lib/trialFilters";
import type { TrialFilterProps } from "./filterTypes";
export function TrialResultFilters({ filters, setters, data }: TrialFilterProps) {
  const {
    hasResults,
    resultEvaluation,
    resultsPostedFrom,
    resultsPostedTo,
    hasKeyResult,
    publicationId,
    conference,
    disclosedFrom,
    disclosedTo,
  } = filters;
  const {
    setHasResults,
    setResultEvaluation,
    setResultsPostedFrom,
    setResultsPostedTo,
    setHasKeyResult,
    setPublicationId,
    setConference,
    setDisclosedFrom,
    setDisclosedTo,
  } = setters;

  return (
    <SecondaryFilters
      label={t("试验结果、日期与发表")}
      activeCount={
        [
          hasResults,
          resultEvaluation,
          resultsPostedFrom,
          resultsPostedTo,
          hasKeyResult,
          publicationId,
          conference,
          disclosedFrom,
          disclosedTo,
        ].filter(Boolean).length
      }
    >
      <label>
        <span>{t("结果发布")}</span>
        <select
          aria-label={t("结果发布")}
          value={hasResults}
          onChange={(event) => {
            const value = event.target.value;
            setHasResults(value);
            if (value === "false") setResultEvaluation("");
          }}
        >
          <option value="">{t("全部")}</option>
          <option value="true">已发布结果 ({data?.facets?.has_results?.true ?? 0})</option>
          <option value="false">尚未发布 ({data?.facets?.has_results?.false ?? 0})</option>
        </select>
      </label>
      <label>
        <span>{t("结果最优评价")}</span>
        <select
          value={resultEvaluation}
          disabled={hasResults === "false"}
          onChange={(event) => setResultEvaluation(event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.entries(resultEvaluationLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({data?.facets?.result_evaluation?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("结果发布日期起")}</span>
        <input
          type="date"
          value={resultsPostedFrom}
          max={resultsPostedTo || undefined}
          onChange={(event) => setResultsPostedFrom(event.target.value)}
        />
      </label>
      <label>
        <span>{t("结果发布日期止")}</span>
        <input
          type="date"
          value={resultsPostedTo}
          min={resultsPostedFrom || undefined}
          onChange={(event) => setResultsPostedTo(event.target.value)}
        />
      </label>
      <label>
        <span>{t("关键结果")}</span>
        <select value={hasKeyResult} onChange={(event) => setHasKeyResult(event.target.value)}>
          <option value="">{t("全部")}</option>
          {Object.entries(keyResultLabels).map(([value, label]) => (
            <option value={value} key={value}>
              {professionalEnumLabel(label, value)} ({data?.facets?.has_key_result?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("发表编号")}</span>
        <input
          value={publicationId}
          onChange={(event) => setPublicationId(event.target.value)}
          placeholder={t("PMID、DOI 或会议摘要编号")}
          maxLength={240}
        />
      </label>
      <label>
        <span>{t("会议")}</span>
        <input value={conference} onChange={(event) => setConference(event.target.value)} maxLength={500} />
      </label>
      <label>
        <span>{t("披露日期起")}</span>
        <input
          type="date"
          value={disclosedFrom}
          max={disclosedTo || undefined}
          onChange={(event) => setDisclosedFrom(event.target.value)}
        />
      </label>
      <label>
        <span>{t("披露日期止")}</span>
        <input
          type="date"
          value={disclosedTo}
          min={disclosedFrom || undefined}
          onChange={(event) => setDisclosedTo(event.target.value)}
        />
      </label>
    </SecondaryFilters>
  );
}
