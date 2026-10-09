import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ClinicalTrialDetailRead } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";
import { clinicalCaption, clinicalText as t } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { trialResultEvaluationLabels as resultEvaluationLabels } from "../../lib/trialFilters";
import { clinicalContentRows } from "./contentRows";
import { formatResultRange } from "./presentation";
import { TrialStatisticalAnalysis } from "./TrialStatisticalAnalysis";
import { disclosureTypeLabels } from "./vocabulary";
export function TrialOutcomes({ data }: { data: ClinicalTrialDetailRead }) {
  return (
    <div className="trial-detail-sections">
      <section className="trial-outcome-list">
        <h3>{t("终点与统计结果")}</h3>
        {data.outcomes.length ? (
          clinicalContentRows(data.outcomes).map(({ value: outcome, key }) => (
            <section key={key}>
              <header>
                <StatusBadge value={outcome.outcome_type ?? t("终点")} />
                <div>
                  <h3>{outcome.measure}</h3>
                  <span>{outcome.time_frame ?? t("时间窗未记录")}</span>
                </div>
              </header>
              {outcome.description ? <p>{outcome.description}</p> : null}
              {outcome.results?.length ? (
                <ScrollableTableRegion ariaLabel={t("结构化结果：{measure}", { measure: outcome.measure })}>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("队列")}</th>
                        <th>{t("结果")}</th>
                        <th>{t("分析人数")}</th>
                        <th>{t("区间/离散度")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {clinicalContentRows(outcome.results).map(({ value: result, key }) => (
                        <tr key={key}>
                          <td>{result.group_label}</td>
                          <td>
                            <strong>{result.value}</strong> {result.unit ?? ""}
                          </td>
                          <td>{result.participants?.toLocaleString(formattingLocale()) ?? "--"}</td>
                          <td>{formatResultRange(result.lower_limit, result.upper_limit, result.dispersion)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ScrollableTableRegion>
              ) : (
                <p className="trial-detail-note">{t("终点已登记，尚未观察到结构化结果。")}</p>
              )}
              {outcome.statistical_analyses?.length ? (
                <div className="trial-analysis-list">
                  {clinicalContentRows(outcome.statistical_analyses).map(({ value: analysis, key }) => (
                    <TrialStatisticalAnalysis key={key} analysis={analysis} />
                  ))}
                </div>
              ) : null}
            </section>
          ))
        ) : (
          <EmptyState title={t("暂无终点记录")} detail={t("当前可用来源未提供结构化终点")} />
        )}
      </section>
      <section>
        <h3>{t("结果披露与版本")}</h3>
        {(data.result_disclosures ?? []).length ? (
          <div className="trial-disclosure-list">
            {(data.result_disclosures ?? []).map((disclosure) => (
              <article key={disclosure.id}>
                <header>
                  <div>
                    <StatusBadge
                      value={disclosure.disclosure_type}
                      label={
                        disclosureTypeLabels[disclosure.disclosure_type]
                          ? clinicalCaption(disclosureTypeLabels[disclosure.disclosure_type])
                          : disclosure.disclosure_type
                      }
                    />
                    {disclosure.is_key_result ? <StatusBadge value={t("关键结果")} /> : null}
                  </div>
                  <span>{formatDate(disclosure.disclosed_at)}</span>
                </header>
                <strong>{disclosure.title}</strong>
                <small>
                  {disclosure.external_id ?? t("无外部编号")} · {t("版本 {version}", { version: disclosure.version })}
                  {disclosure.conference_name ? ` · ${disclosure.conference_name}` : ""}
                </small>
                {disclosure.result_evaluation ? (
                  <span>
                    {resultEvaluationLabels[disclosure.result_evaluation]
                      ? professionalEnumLabel(
                          resultEvaluationLabels[disclosure.result_evaluation],
                          disclosure.result_evaluation,
                        )
                      : disclosure.result_evaluation}
                  </span>
                ) : null}
                {disclosure.source_quote ? <p>{disclosure.source_quote}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title={t("暂无结果披露记录")} detail={t("试验可保留注册结果，披露版本仅在来源明确提供时入库")} />
        )}
      </section>
    </div>
  );
}
