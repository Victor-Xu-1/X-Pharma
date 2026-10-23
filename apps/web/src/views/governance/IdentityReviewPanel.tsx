import { Check, GitMerge, History, Split, X } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ResearchTabList } from "../../components/ResearchTabList";
import { governanceReviewText as t } from "../../lib/i18n/governanceReview";
import { IdentityImpactPanel } from "./IdentityImpactPanel";
import { ReviewNotes } from "./ReviewNotes";
import type { GovernanceReviewController } from "./useGovernanceReview";

export function IdentityReviewPanel({ review }: { review: GovernanceReviewController }) {
  const {
    identityScope,
    identityHistory,
    history,
    identityCases,
    visibleIdentityCases,
    selectedIdentity: selected,
    identityImpact,
    impact,
    impactError,
    canonicalEntityId,
    notes,
    busy,
    error,
    identityReady,
  } = review;
  const loading = identityScope === "history" && !history && identityHistory.isPending;
  const historyError =
    identityScope === "history" && identityHistory.error instanceof Error ? identityHistory.error.message : "";
  return (
    <>
      <div className="identity-scope-toolbar">
        <ResearchTabList
          idPrefix="identity-scope"
          ariaLabel={t("实体消歧范围")}
          className="identity-scope-control"
          activeTab={identityScope}
          onChange={review.changeIdentityScope}
          tabs={[
            {
              key: "pending",
              label: t("待处理 {count}", { count: identityCases.length }),
              icon: <GitMerge size={15} />,
              panelId: "identity-results-panel",
              disabled: busy,
            },
            {
              key: "history",
              label: `${t("历史与回滚")}${history ? ` ${history.length}` : ""}`,
              icon: <History size={15} />,
              panelId: "identity-results-panel",
              disabled: busy,
            },
          ]}
        />
        <p>{t("规范实体合并不迁移或覆盖领域事实；拆分通过停用可逆 canonical link 恢复独立身份。")}</p>
      </div>
      <div role="tabpanel" id="identity-results-panel" aria-labelledby={`identity-scope-tab-${identityScope}`}>
        {loading ? <Spinner label={t("正在读取实体消歧历史")} /> : null}
        {historyError ? <ErrorState message={historyError} retry={() => void identityHistory.refetch()} /> : null}
        {!loading && !historyError && !visibleIdentityCases.length ? (
          <EmptyState title={t(identityScope === "pending" ? "当前没有待审核实体冲突" : "当前没有实体消歧历史")} />
        ) : null}
        {visibleIdentityCases.length ? (
          <section className="governance-layout">
            <aside className="review-list" aria-label={t("实体消歧范围")}>
              <div className="review-list-head">
                {identityScope === "pending" ? <GitMerge size={19} /> : <History size={19} />}
                <span>
                  {t(identityScope === "pending" ? "{count} 项待消歧" : "{count} 项历史决策", {
                    count: visibleIdentityCases.length,
                  })}
                </span>
              </div>
              {visibleIdentityCases.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={selected?.id === item.id ? "active" : ""}
                  aria-pressed={selected?.id === item.id}
                  disabled={busy}
                  onClick={() => review.selectIdentity(item.id)}
                >
                  <div>
                    <strong>{item.source_entity_name}</strong>
                    <StatusBadge value={identityScope === "pending" ? item.risk_tier : item.status} />
                  </div>
                  <p>{t("候选规范实体：{name}", { name: item.candidate_entity_name })}</p>
                  <small>
                    {t("匹配分 {score}%", { score: (item.score * 100).toFixed(1) })} ·{" "}
                    {formatDate(item.created_at, true)}
                  </small>
                </button>
              ))}
            </aside>
            <article className="review-detail">
              {selected ? (
                <>
                  <header>
                    <div>
                      <p className="review-kind">{t("规范实体候选")}</p>
                      <h2>{selected.source_entity_name}</h2>
                    </div>
                    <StatusBadge value={selected.status} />
                  </header>
                  <section>
                    <h3>{t("规范实体候选")}</h3>
                    <dl className="review-source">
                      <div>
                        <dt>{t("来源实体")}</dt>
                        <dd>{selected.source_entity_name}</dd>
                      </div>
                      <div>
                        <dt>{t("候选实体")}</dt>
                        <dd>{selected.candidate_entity_name}</dd>
                      </div>
                      <div>
                        <dt>{t("风险等级")}</dt>
                        <dd>
                          <StatusBadge value={selected.risk_tier} />
                        </dd>
                      </div>
                      <div>
                        <dt>{t("当前状态")}</dt>
                        <dd>
                          <StatusBadge value={selected.status} />
                        </dd>
                      </div>
                    </dl>
                    <p className="field-help">{t("匹配分 {score}%", { score: (selected.score * 100).toFixed(1) })}</p>
                  </section>
                  <details className="identity-matching-evidence">
                    <summary>{t("判定依据")}</summary>
                    <pre className="json-preview compact">{JSON.stringify(selected.reasons, null, 2)}</pre>
                  </details>
                  {identityImpact.isPending ? <Spinner label={t("正在分析跨域引用")} /> : null}
                  {impactError ? (
                    <ErrorState message={impactError} retry={() => void identityImpact.refetch()} />
                  ) : null}
                  {impact ? (
                    <IdentityImpactPanel
                      impact={impact}
                      onRefresh={() => void identityImpact.refetch()}
                      refreshing={busy || identityImpact.isFetching}
                    />
                  ) : null}
                  {selected.status === "pending" && impact ? (
                    <label className="canonical-choice">
                      <span>{t("规范实体保留")}</span>
                      <select
                        aria-label={t("规范实体保留")}
                        value={canonicalEntityId}
                        disabled={busy || !identityReady}
                        onChange={(event) => review.setCanonicalEntityId(event.target.value)}
                      >
                        <option value={selected.source_entity_id}>{selected.source_entity_name}</option>
                        <option value={selected.candidate_entity_id}>{selected.candidate_entity_name}</option>
                      </select>
                      <small>
                        {t("系统建议：{name}。建议只提供决策依据，不自动批准。", {
                          name:
                            impact.recommended_canonical_entity_id === selected.source_entity_id
                              ? selected.source_entity_name
                              : impact.recommended_canonical_entity_id === selected.candidate_entity_id
                                ? selected.candidate_entity_name
                                : impact.recommended_canonical_entity_id,
                        })}
                      </small>
                    </label>
                  ) : null}
                  {selected.status === "pending" || selected.status === "approved" ? (
                    <>
                      <ReviewNotes
                        label={t(selected.status === "approved" ? "拆分恢复依据" : "审核意见")}
                        notes={notes}
                        onNotes={review.setNotes}
                        busy={busy}
                        error={error}
                      />
                      <div className="decision-bar">
                        {selected.status === "pending" ? (
                          <>
                            <button
                              className="danger-button"
                              type="button"
                              disabled={busy || !identityReady}
                              onClick={() => review.decideIdentity("reject")}
                            >
                              <X size={17} />
                              {t("保持独立")}
                            </button>
                            <button
                              className="primary-button"
                              type="button"
                              disabled={busy || !identityReady || !canonicalEntityId}
                              onClick={() => review.decideIdentity("approve")}
                            >
                              <Check size={17} />
                              {t("设为同一实体")}
                            </button>
                          </>
                        ) : (
                          <button
                            className="danger-button"
                            type="button"
                            disabled={busy || !identityReady || !impact?.rollback_available}
                            onClick={() => review.decideIdentity("revert")}
                          >
                            <Split size={17} />
                            {t("拆分并恢复独立实体")}
                          </button>
                        )}
                      </div>
                    </>
                  ) : null}
                </>
              ) : null}
            </article>
          </section>
        ) : null}
      </div>
    </>
  );
}
