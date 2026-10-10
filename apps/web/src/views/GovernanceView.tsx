import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, GitMerge, History, ShieldCheck, Split, X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { FactQualityFindings } from "../components/FactQualityFindings";
import { FactReviewComparison } from "../components/FactReviewComparison";
import { QualityOperationsPanel } from "../components/QualityOperationsPanel";
import { ResearchTabList } from "../components/ResearchTabList";
import {
  decideEntityResolution,
  decideStagedFact,
  type GovernanceRunStatus,
  governanceKeys,
  loadEntityResolutionHistory,
  loadEntityResolutionImpact,
  loadGovernanceQueues,
  loadGovernanceRuns,
} from "../lib/contracts/governance";
import { governanceLabel, groupReviewFacts } from "../lib/governancePresentation";
import { GovernanceRunsPanel } from "./governance/GovernanceRunsPanel";
import { IdentityImpactPanel } from "./governance/IdentityImpactPanel";
import { PublicationBatchPanel } from "./governance/PublicationBatchPanel";

export function GovernanceView() {
  const [mode, setMode] = useState<"facts" | "identity" | "quality" | "runs">("facts");
  const [selectedFactId, setSelectedFactId] = useState("");
  const [selectedIdentityId, setSelectedIdentityId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [identityScope, setIdentityScope] = useState<"pending" | "history">("pending");
  const [canonicalEntityId, setCanonicalEntityId] = useState("");
  const [runStatus, setRunStatus] = useState<GovernanceRunStatus | "all">("all");
  const [runOffset, setRunOffset] = useState(0);
  const [notes, setNotes] = useState("");
  const [validationError, setValidationError] = useState("");
  const queues = useQuery({
    queryKey: governanceKeys.queues,
    queryFn: ({ signal }) => loadGovernanceQueues(signal),
  });
  const runLimit = 30;
  const runs = useQuery({
    queryKey: governanceKeys.runs(runStatus, runLimit, runOffset),
    queryFn: ({ signal }) => loadGovernanceRuns(runStatus, runLimit, runOffset, signal),
    enabled: mode === "runs",
  });
  const identityHistory = useQuery({
    queryKey: governanceKeys.identityHistory,
    queryFn: ({ signal }) => loadEntityResolutionHistory(signal),
    enabled: mode === "identity",
  });
  const facts = queues.data?.facts ?? [];
  const identityCases = queues.data?.identityCases ?? [];
  const visibleIdentityCases = identityScope === "pending" ? identityCases : (identityHistory.data ?? []);
  const selected = facts.find((item) => item.id === selectedFactId) ?? facts[0] ?? null;
  const selectedIdentity =
    visibleIdentityCases.find((item) => item.id === selectedIdentityId) ?? visibleIdentityCases[0] ?? null;
  const identityImpact = useQuery({
    queryKey: governanceKeys.identityImpact(selectedIdentity?.id ?? "none"),
    queryFn: ({ signal }) => loadEntityResolutionImpact(selectedIdentity?.id ?? "", signal),
    enabled: mode === "identity" && Boolean(selectedIdentity),
  });

  useEffect(() => {
    if (!selectedIdentity || !identityImpact.data) {
      setCanonicalEntityId("");
      return;
    }
    setCanonicalEntityId(identityImpact.data.recommended_canonical_entity_id);
  }, [selectedIdentity, identityImpact.data]);

  const factDecision = useMutation({
    mutationFn: decideStagedFact,
    onSuccess: async () => {
      setNotes("");
      await queues.refetch();
    },
  });
  const identityDecision = useMutation({
    mutationFn: decideEntityResolution,
    onSuccess: async () => {
      setNotes("");
      await Promise.all([queues.refetch(), identityHistory.refetch(), identityImpact.refetch()]);
    },
  });
  const mutationError = factDecision.error ?? identityDecision.error;
  const error = validationError || (mutationError instanceof Error ? mutationError.message : "");
  const busy = factDecision.isPending || identityDecision.isPending;

  function clearFeedback() {
    setValidationError("");
    factDecision.reset();
    identityDecision.reset();
  }

  function decide(decision: "approve" | "reject") {
    if (!selected) return;
    if ((decision === "reject" || selected.status === "conflict") && !notes.trim()) {
      setValidationError(decision === "reject" ? "拒绝时必须填写原因" : "冲突事实批准前必须填写审核意见");
      return;
    }
    clearFeedback();
    factDecision.mutate({ stagedFactId: selected.id, decision, notes });
  }

  function decideIdentity(action: "approve" | "reject" | "revert") {
    if (!selectedIdentity) return;
    if (!notes.trim()) {
      setValidationError(
        action === "reject"
          ? "保持实体独立时必须填写原因"
          : action === "revert"
            ? "拆分恢复前必须填写依据"
            : "设为同一实体时必须填写审核依据",
      );
      return;
    }
    if (action === "approve" && !canonicalEntityId) {
      setValidationError("必须选择保留的规范实体");
      return;
    }
    clearFeedback();
    identityDecision.mutate({
      caseId: selectedIdentity.id,
      action,
      expectedStatus: selectedIdentity.status,
      canonicalEntityId: action === "approve" ? canonicalEntityId : null,
      notes,
    });
  }

  if (!queues.data && !queues.error) return <Spinner label="正在读取数据审核队列" />;
  if (queues.error && !queues.data) {
    const message = queues.error instanceof Error ? queues.error.message : "审核队列加载失败";
    return <ErrorState message={message} retry={() => void queues.refetch()} />;
  }
  const tabs = (
    <ResearchTabList
      idPrefix="governance"
      ariaLabel="治理队列"
      className="governance-tabs"
      activeTab={mode}
      onChange={(next) => {
        setMode(next);
        setNotes("");
        clearFeedback();
      }}
      tabs={[
        { key: "facts", label: `事实审核 ${facts.length}`, panelId: "governance-active-panel" },
        { key: "identity", label: `实体消歧 ${identityCases.length}`, panelId: "governance-active-panel" },
        { key: "quality", label: "质量运营", panelId: "governance-active-panel" },
        {
          key: "runs",
          label: `运行追踪${runs.data ? ` ${runs.data.total}` : ""}`,
          panelId: "governance-active-panel",
        },
      ]}
    />
  );
  const renderPanel = (content: ReactNode) => (
    <>
      {tabs}
      <div role="tabpanel" id="governance-active-panel" aria-labelledby={`governance-tab-${mode}`}>
        {content}
      </div>
    </>
  );
  if (mode === "quality") {
    return renderPanel(<QualityOperationsPanel />);
  }
  if (mode === "runs") {
    return renderPanel(
      <>
        <GovernanceRunsPanel
          page={runs.data ?? null}
          loading={!runs.data && !runs.error}
          error={runs.error instanceof Error ? runs.error.message : ""}
          status={runStatus}
          offset={runOffset}
          selectedRunId={selectedRunId}
          onStatus={(value) => {
            setRunStatus(value);
            setRunOffset(0);
            setSelectedRunId("");
          }}
          onOffset={setRunOffset}
          onSelect={setSelectedRunId}
          onRetry={() => void runs.refetch()}
        />
      </>,
    );
  }
  if (mode === "identity") {
    const identityLoading = identityScope === "history" && identityHistory.isPending;
    const identityError = identityHistory.error instanceof Error ? identityHistory.error.message : "";
    return renderPanel(
      <>
        <div className="identity-scope-toolbar">
          <ResearchTabList
            idPrefix="identity-scope"
            ariaLabel="实体消歧范围"
            className="identity-scope-control"
            activeTab={identityScope}
            onChange={(next) => {
              setIdentityScope(next);
              setSelectedIdentityId("");
              setNotes("");
              clearFeedback();
            }}
            tabs={[
              {
                key: "pending",
                label: `待处理 ${identityCases.length}`,
                icon: <GitMerge size={15} />,
                panelId: "identity-results-panel",
              },
              {
                key: "history",
                label: `历史与回滚 ${identityHistory.data?.length ?? 0}`,
                icon: <History size={15} />,
                panelId: "identity-results-panel",
              },
            ]}
          />
          <p>规范实体合并不迁移或覆盖领域事实；拆分通过停用可逆 canonical link 恢复独立身份。</p>
        </div>
        <div role="tabpanel" id="identity-results-panel" aria-labelledby={`identity-scope-tab-${identityScope}`}>
          {identityLoading ? <Spinner label="正在读取实体消歧历史" /> : null}
          {identityError && !identityHistory.data ? (
            <ErrorState message={identityError} retry={() => void identityHistory.refetch()} />
          ) : null}
          {!identityLoading && !identityError && !visibleIdentityCases.length ? (
            <EmptyState title={identityScope === "pending" ? "当前没有待审核实体冲突" : "当前没有实体消歧历史"} />
          ) : null}
          {visibleIdentityCases.length ? (
            <section className="governance-layout">
              <aside className="review-list">
                <div className="review-list-head">
                  {identityScope === "pending" ? <GitMerge size={19} /> : <History size={19} />}
                  <span>
                    <strong>{visibleIdentityCases.length}</strong>
                    {identityScope === "pending" ? " 项待消歧" : " 项历史决策"}
                  </span>
                </div>
                {visibleIdentityCases.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={selectedIdentity?.id === item.id ? "active" : ""}
                    onClick={() => {
                      setSelectedIdentityId(item.id);
                      setNotes("");
                      clearFeedback();
                    }}
                  >
                    <div>
                      <strong>{item.source_entity_name}</strong>
                      <StatusBadge value={identityScope === "pending" ? item.risk_tier : item.status} />
                    </div>
                    <p>候选规范实体：{item.candidate_entity_name}</p>
                    <small>
                      匹配分 {(item.score * 100).toFixed(1)}% · {formatDate(item.created_at, true)}
                    </small>
                  </button>
                ))}
              </aside>
              <article className="review-detail">
                {selectedIdentity ? (
                  <>
                    <header>
                      <div>
                        <p className="eyebrow">ENTITY RESOLUTION</p>
                        <h2>{selectedIdentity.source_entity_name}</h2>
                      </div>
                      <span className="confidence-score">
                        {(selectedIdentity.score * 100).toFixed(1)}
                        <small>%</small>
                      </span>
                    </header>
                    <section>
                      <h3>规范实体候选</h3>
                      <dl className="review-source">
                        <div>
                          <dt>来源实体</dt>
                          <dd>{selectedIdentity.source_entity_name}</dd>
                        </div>
                        <div>
                          <dt>候选实体</dt>
                          <dd>{selectedIdentity.candidate_entity_name}</dd>
                        </div>
                        <div>
                          <dt>风险等级</dt>
                          <dd>
                            <StatusBadge value={selectedIdentity.risk_tier} />
                          </dd>
                        </div>
                        <div>
                          <dt>当前状态</dt>
                          <dd>
                            <StatusBadge value={selectedIdentity.status} />
                          </dd>
                        </div>
                      </dl>
                    </section>
                    <section>
                      <h3>判定依据</h3>
                      <pre className="json-preview compact">{JSON.stringify(selectedIdentity.reasons, null, 2)}</pre>
                    </section>
                    {identityImpact.isPending ? <Spinner label="正在分析跨域引用" /> : null}
                    {identityImpact.error instanceof Error ? (
                      <ErrorState message={identityImpact.error.message} retry={() => void identityImpact.refetch()} />
                    ) : null}
                    {identityImpact.data ? <IdentityImpactPanel impact={identityImpact.data} /> : null}
                    {selectedIdentity.status === "pending" && identityImpact.data ? (
                      <label className="canonical-choice">
                        <span>规范实体保留</span>
                        <select
                          value={canonicalEntityId}
                          onChange={(event) => setCanonicalEntityId(event.target.value)}
                        >
                          <option value={selectedIdentity.source_entity_id}>
                            {selectedIdentity.source_entity_name}
                          </option>
                          <option value={selectedIdentity.candidate_entity_id}>
                            {selectedIdentity.candidate_entity_name}
                          </option>
                        </select>
                        <small>
                          系统建议：
                          {identityImpact.data.recommended_canonical_entity_id === selectedIdentity.source_entity_id
                            ? selectedIdentity.source_entity_name
                            : selectedIdentity.candidate_entity_name}
                          。建议只提供决策依据，不自动批准。
                        </small>
                      </label>
                    ) : null}
                    {selectedIdentity.status === "pending" || selectedIdentity.status === "approved" ? (
                      <>
                        <label className="review-notes">
                          <span>{selectedIdentity.status === "approved" ? "拆分恢复依据" : "审核意见"}</span>
                          <textarea
                            rows={4}
                            value={notes}
                            onChange={(event) => setNotes(event.target.value)}
                            maxLength={4000}
                          />
                        </label>
                        {error ? (
                          <p className="form-error" role="alert">
                            {error}
                          </p>
                        ) : null}
                        {selectedIdentity.status === "pending" ? (
                          <div className="decision-bar">
                            <button
                              className="danger-button"
                              type="button"
                              disabled={busy}
                              onClick={() => void decideIdentity("reject")}
                            >
                              <X size={17} />
                              保持独立
                            </button>
                            <button
                              className="primary-button"
                              type="button"
                              disabled={busy || !identityImpact.data}
                              onClick={() => void decideIdentity("approve")}
                            >
                              <Check size={17} />
                              设为同一实体
                            </button>
                          </div>
                        ) : (
                          <div className="decision-bar">
                            <button
                              className="danger-button"
                              type="button"
                              disabled={busy || !identityImpact.data?.rollback_available}
                              onClick={() => void decideIdentity("revert")}
                            >
                              <Split size={17} />
                              拆分并恢复独立实体
                            </button>
                          </div>
                        )}
                      </>
                    ) : null}
                  </>
                ) : null}
              </article>
            </section>
          ) : null}
        </div>
      </>,
    );
  }
  if (!facts?.length)
    return renderPanel(
      <>
        <PublicationBatchPanel facts={facts} onQueuesChanged={() => void queues.refetch()} />
        <EmptyState title="当前没有待审核事实" />
      </>,
    );
  return renderPanel(
    <>
      <PublicationBatchPanel facts={facts} onQueuesChanged={() => void queues.refetch()} />
      <section className="governance-layout">
        <aside className="review-list">
          <div className="review-list-head">
            <ShieldCheck size={19} />
            <span>
              <strong>{facts.length}</strong> 项待审核
            </span>
          </div>
          {groupReviewFacts(facts).map((group) => (
            <details key={group[0].id} open>
              <summary>
                {governanceLabel(group[0].fact_kind)} · {group.length} 条候选
              </summary>
              {group.map((fact) => (
                <button
                  key={fact.id}
                  type="button"
                  className={selected?.id === fact.id ? "active" : ""}
                  onClick={() => {
                    setSelectedFactId(fact.id);
                    setNotes("");
                    clearFeedback();
                  }}
                >
                  <div>
                    <strong>{governanceLabel(fact.fact_kind)}</strong>
                    <StatusBadge value={fact.status} />
                  </div>
                  <p>{fact.source_quote}</p>
                  <small>{formatDate(fact.created_at, true)} · 引证待核对</small>
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
                  <p className="eyebrow">STAGED FACT</p>
                  <h2>{governanceLabel(selected.fact_kind)}</h2>
                </div>
                <StatusBadge value={selected.status} />
              </header>
              <FactReviewComparison fact={selected} />
              <section>
                <h3>原文引证</h3>
                <blockquote>{selected.source_quote}</blockquote>
                <dl className="review-source">
                  <div>
                    <dt>文档</dt>
                    <dd className="mono-cell">{selected.source_document_id ?? "--"}</dd>
                  </div>
                  <div>
                    <dt>定位</dt>
                    <dd>{selected.source_locator ?? "--"}</dd>
                  </div>
                </dl>
              </section>
              {selected.quality_findings.length ? <FactQualityFindings findings={selected.quality_findings} /> : null}
              <label className="review-notes">
                <span>审核意见</span>
                <textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} maxLength={4000} />
              </label>
              {error ? (
                <p className="form-error" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="decision-bar">
                <button className="danger-button" type="button" disabled={busy} onClick={() => void decide("reject")}>
                  <X size={17} />
                  拒绝
                </button>
                <button className="primary-button" type="button" disabled={busy} onClick={() => void decide("approve")}>
                  <Check size={17} />
                  批准并发布
                </button>
              </div>
            </>
          ) : null}
        </article>
      </section>
    </>,
  );
}
