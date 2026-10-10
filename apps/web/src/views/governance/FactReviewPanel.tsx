import { Check, ShieldCheck, X } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { FactQualityFindings } from "../../components/FactQualityFindings";
import { FactReviewComparison } from "../../components/FactReviewComparison";
import { governanceLabel, groupReviewFacts, reviewFactTitle } from "../../lib/governancePresentation";
import { governanceReviewText as t } from "../../lib/i18n/governanceReview";
import { ReviewNotes } from "./ReviewNotes";
import type { GovernanceReviewController } from "./useGovernanceReview";

export function FactReviewPanel({ review }: { review: GovernanceReviewController }) {
  const { facts, selected, notes, busy, error, factReady } = review;
  if (!facts.length) return <EmptyState title={t("当前没有待审核事实")} />;
  return (
    <section className="governance-layout">
      <aside className="review-list" aria-label={t("事实审核 {count}", { count: facts.length })}>
        <div className="review-list-head">
          <ShieldCheck size={19} />
          <span>{t("{count} 项待审核", { count: facts.length })}</span>
        </div>
        {groupReviewFacts(facts).map((group) => (
          <details key={group[0].id} open>
            <summary>
              {reviewFactTitle(group[0])} ·{" "}
              {group.length === 1 ? t("1 条候选") : t("{count} 条候选", { count: group.length })}
            </summary>
            {group.map((fact) => (
              <button
                key={fact.id}
                type="button"
                className={selected?.id === fact.id ? "active" : ""}
                aria-pressed={selected?.id === fact.id}
                disabled={busy}
                onClick={() => review.selectFact(fact.id)}
              >
                <div>
                  <strong>{reviewFactTitle(fact)}</strong>
                  <StatusBadge value={fact.status} />
                </div>
                <p>{fact.source_quote}</p>
                <small>
                  {formatDate(fact.created_at, true)} · {t("引证待核对")}
                </small>
              </button>
            ))}
          </details>
        ))}
      </aside>
      <article className="review-detail">
        {selected ? (
          <>
            <header>
              <div>
                <p className="review-kind">{governanceLabel(selected.fact_kind)}</p>
                <h2>{reviewFactTitle(selected)}</h2>
              </div>
              <StatusBadge value={selected.status} />
            </header>
            <FactReviewComparison
              fact={selected}
              comparison={review.factComparison}
              onRetry={() => void review.factComparison.refetch()}
            />
            <section>
              <h3>{t("原文引证")}</h3>
              <blockquote>{selected.source_quote}</blockquote>
              <dl className="review-source">
                <div>
                  <dt>{t("文档")}</dt>
                  <dd className="mono-cell">{selected.source_document_id ?? t("未提供")}</dd>
                </div>
                <div>
                  <dt>{t("定位")}</dt>
                  <dd>{selected.source_locator ?? t("未提供")}</dd>
                </div>
              </dl>
            </section>
            {selected.quality_findings.length ? <FactQualityFindings findings={selected.quality_findings} /> : null}
            <ReviewNotes notes={notes} onNotes={review.setNotes} busy={busy} error={error} />
            <div className="decision-bar">
              <button
                className="danger-button"
                type="button"
                disabled={busy || !factReady}
                onClick={() => review.decide("reject")}
              >
                <X size={17} />
                {t("拒绝")}
              </button>
              <button
                className="primary-button"
                type="button"
                disabled={busy || !factReady}
                onClick={() => review.decide("approve")}
              >
                <Check size={17} />
                {t("批准并发布")}
              </button>
            </div>
          </>
        ) : null}
      </article>
    </section>
  );
}
