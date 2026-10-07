import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Database,
  GitMerge,
  History,
  RotateCcw,
  ShieldCheck,
  Split,
  X,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { FactQualityFindings } from "../components/FactQualityFindings";
import { FactReviewComparison } from "../components/FactReviewComparison";
import { QualityOperationsPanel } from "../components/QualityOperationsPanel";
import { ResearchTabList } from "../components/ResearchTabList";
import {
  commitPublicationBatch,
  decideEntityResolution,
  decideStagedFact,
  type EntityResolutionImpact,
  type GovernanceRun,
  type GovernanceRunStatus,
  governanceKeys,
  loadEntityResolutionHistory,
  loadEntityResolutionImpact,
  loadGovernanceQueues,
  loadGovernanceRuns,
  loadProjectionMaintenanceAccess,
  loadProjectionMaintenanceJobs,
  loadPublicationBatch,
  loadPublicationBatches,
  type PublicationBatch,
  previewPublicationBatch,
  requestProjectionMaintenance,
  type StagedFact,
} from "../lib/contracts/governance";
import { governanceLabel, groupReviewFacts } from "../lib/governancePresentation";

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

function PublicationBatchPanel({ facts, onQueuesChanged }: { facts: StagedFact[]; onQueuesChanged: () => void }) {
  const [selectedFactIds, setSelectedFactIds] = useState<string[]>([]);
  const [activeBatchId, setActiveBatchId] = useState("");
  const [batchReason, setBatchReason] = useState("");
  const [localError, setLocalError] = useState("");
  const batches = useQuery({
    queryKey: governanceKeys.publicationBatches,
    queryFn: ({ signal }) => loadPublicationBatches(signal),
  });
  const activeBatch = useQuery({
    queryKey: governanceKeys.publicationBatch(activeBatchId || "none"),
    queryFn: ({ signal }) => loadPublicationBatch(activeBatchId, signal),
    enabled: Boolean(activeBatchId),
  });
  const maintenanceAccess = useQuery({
    queryKey: governanceKeys.projectionMaintenanceAccess,
    queryFn: ({ signal }) => loadProjectionMaintenanceAccess(signal),
  });
  const maintenanceJobs = useQuery({
    queryKey: governanceKeys.projectionMaintenanceJobs,
    queryFn: ({ signal }) => loadProjectionMaintenanceJobs(signal),
    enabled: maintenanceAccess.data === true,
    refetchInterval: (query) =>
      query.state.data?.some((job) => job.status === "queued" || job.status === "running") ? 3000 : false,
  });
  const previewMutation = useMutation({
    mutationFn: previewPublicationBatch,
    onSuccess: async (batch) => {
      setActiveBatchId(batch.id);
      setLocalError("");
      await batches.refetch();
    },
  });
  const commitMutation = useMutation({
    mutationFn: commitPublicationBatch,
    onSuccess: async (batch) => {
      setSelectedFactIds([]);
      setBatchReason("");
      setActiveBatchId(batch.id);
      onQueuesChanged();
      await Promise.all([batches.refetch(), activeBatch.refetch()]);
    },
  });
  const maintenanceMutation = useMutation({
    mutationFn: requestProjectionMaintenance,
    onSuccess: async () => {
      setLocalError("");
      await maintenanceJobs.refetch();
    },
  });
  const error =
    localError ||
    (previewMutation.error instanceof Error ? previewMutation.error.message : "") ||
    (commitMutation.error instanceof Error ? commitMutation.error.message : "");
  const maintenanceError = maintenanceMutation.error instanceof Error ? maintenanceMutation.error.message : "";
  const busy = previewMutation.isPending || commitMutation.isPending || maintenanceMutation.isPending;

  function newIdempotencyKey(operation: "publish" | "withdraw") {
    return `governance-ui:${operation}:${globalThis.crypto.randomUUID()}`;
  }

  function previewPublish() {
    if (!selectedFactIds.length) {
      setLocalError("请先选择至少一项待审事实");
      return;
    }
    if (!batchReason.trim()) {
      setLocalError("批次发布必须填写审核依据");
      return;
    }
    setLocalError("");
    previewMutation.mutate({
      operation: "publish",
      stagedFactIds: selectedFactIds,
      idempotencyKey: newIdempotencyKey("publish"),
      reason: batchReason,
    });
  }

  function previewWithdrawal(batch: PublicationBatch) {
    if (!batchReason.trim()) {
      setLocalError("批次撤回必须填写具体依据");
      return;
    }
    if (!batch.items?.length) {
      setLocalError("请等待批次明细加载完成");
      return;
    }
    setLocalError("");
    previewMutation.mutate({
      operation: "withdraw",
      stagedFactIds: batch.items.map((item) => item.staged_fact_id),
      idempotencyKey: newIdempotencyKey("withdraw"),
      reason: batchReason,
    });
  }

  const selectedBatch = activeBatch.data ?? null;
  return (
    <details className="publication-control">
      <summary>
        <span>
          <ClipboardCheck size={16} />
          批次发布与撤回
        </span>
        <small>{batches.data?.length ?? 0} 个治理批次</small>
      </summary>
      <div className="publication-control-body">
        <section className="publication-selection" aria-labelledby="publication-selection-title">
          <header>
            <div>
              <h3 id="publication-selection-title">待审事实选择</h3>
              <p>先生成固定预览，再按同一 preview hash 原子提交。</p>
            </div>
            <button
              type="button"
              className="text-button"
              disabled={!facts.length}
              onClick={() =>
                setSelectedFactIds(selectedFactIds.length === facts.length ? [] : facts.map((fact) => fact.id))
              }
            >
              {selectedFactIds.length === facts.length && facts.length ? "取消全选" : "全选"}
            </button>
          </header>
          {facts.length ? (
            <div className="publication-fact-list">
              {facts.map((fact) => (
                <label key={fact.id}>
                  <input
                    type="checkbox"
                    checked={selectedFactIds.includes(fact.id)}
                    onChange={(event) =>
                      setSelectedFactIds((current) =>
                        event.target.checked ? [...current, fact.id] : current.filter((id) => id !== fact.id),
                      )
                    }
                  />
                  <span>
                    <strong>{fact.fact_kind}</strong>
                    <small>{fact.source_quote}</small>
                  </span>
                  <StatusBadge value={fact.status} />
                </label>
              ))}
            </div>
          ) : (
            <p className="field-help">当前没有可加入发布批次的待审事实。</p>
          )}
          <label className="publication-reason">
            <span>批次审核依据</span>
            <textarea
              rows={3}
              maxLength={4000}
              value={batchReason}
              onChange={(event) => setBatchReason(event.target.value)}
            />
          </label>
          <button className="primary-button" type="button" disabled={busy} onClick={previewPublish}>
            <ClipboardCheck size={16} />
            生成发布预览 ({selectedFactIds.length})
          </button>
        </section>
        <section className="publication-history" aria-labelledby="publication-history-title">
          <header>
            <h3 id="publication-history-title">批次历史</h3>
            <button className="icon-button" type="button" title="刷新批次历史" onClick={() => void batches.refetch()}>
              <RotateCcw size={15} />
            </button>
          </header>
          {batches.isPending ? <Spinner label="正在读取发布批次" /> : null}
          {batches.error instanceof Error ? (
            <ErrorState message={batches.error.message} retry={() => void batches.refetch()} />
          ) : null}
          <div className="publication-batch-list">
            {(batches.data ?? []).map((batch) => (
              <button
                key={batch.id}
                type="button"
                className={activeBatchId === batch.id ? "active" : ""}
                onClick={() => setActiveBatchId(batch.id)}
              >
                <span>
                  <strong>{batch.operation === "publish" ? "发布" : "撤回"}</strong>
                  <StatusBadge value={batch.status} />
                </span>
                <small>
                  {batch.expected_count} 项 · {formatDate(batch.created_at, true)}
                </small>
              </button>
            ))}
          </div>
        </section>
        <section className="publication-preview" aria-labelledby="publication-preview-title">
          <h3 id="publication-preview-title">固定预览</h3>
          {activeBatch.isFetching ? <Spinner label="正在读取批次明细" /> : null}
          {activeBatch.error instanceof Error ? (
            <ErrorState message={activeBatch.error.message} retry={() => void activeBatch.refetch()} />
          ) : null}
          {selectedBatch ? (
            <>
              <dl>
                <div>
                  <dt>操作</dt>
                  <dd>{selectedBatch.operation === "publish" ? "批次发布" : "批次撤回"}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>
                    <StatusBadge value={selectedBatch.status} />
                  </dd>
                </div>
                <div>
                  <dt>阻塞项</dt>
                  <dd>{selectedBatch.blocked_count}</dd>
                </div>
              </dl>
              <code>{selectedBatch.preview_sha256}</code>
              <div className="publication-preview-items">
                {(selectedBatch.items ?? []).map((item) => (
                  <article key={item.id}>
                    <span>
                      <strong>{item.snapshot.fact_kind ?? item.staged_fact_id}</strong>
                      <StatusBadge value={item.outcome} />
                    </span>
                    {item.blockers.map((blocker) => (
                      <p key={`${item.id}:${JSON.stringify(blocker)}`}>{String(blocker.code)}</p>
                    ))}
                  </article>
                ))}
              </div>
              {selectedBatch.status === "previewed" ? (
                <button
                  className="primary-button"
                  type="button"
                  disabled={busy || selectedBatch.blocked_count > 0}
                  onClick={() =>
                    commitMutation.mutate({ batchId: selectedBatch.id, previewSha256: selectedBatch.preview_sha256 })
                  }
                >
                  <Check size={16} />
                  原子提交{selectedBatch.operation === "publish" ? "发布" : "撤回"}
                </button>
              ) : null}
              {selectedBatch.status === "committed" && selectedBatch.operation === "publish" ? (
                <button
                  className="danger-button"
                  type="button"
                  disabled={busy}
                  onClick={() => previewWithdrawal(selectedBatch)}
                >
                  <RotateCcw size={16} />
                  基于此批次生成撤回预览
                </button>
              ) : null}
            </>
          ) : (
            <p className="field-help">选择历史批次或生成新预览以查看逐项结果。</p>
          )}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
      </div>
      {maintenanceAccess.data === true ? (
        <ProjectionMaintenancePanel
          jobs={maintenanceJobs.data ?? []}
          loading={maintenanceJobs.isPending}
          error={maintenanceError || (maintenanceJobs.error instanceof Error ? maintenanceJobs.error.message : "")}
          busy={maintenanceMutation.isPending}
          onRequest={(operation) => maintenanceMutation.mutate(operation)}
          onRefresh={() => void maintenanceJobs.refetch()}
        />
      ) : null}
    </details>
  );
}

function ProjectionMaintenancePanel({
  jobs,
  loading,
  error,
  busy,
  onRequest,
  onRefresh,
}: {
  jobs: Awaited<ReturnType<typeof loadProjectionMaintenanceJobs>>;
  loading: boolean;
  error: string;
  busy: boolean;
  onRequest: (operation: "consistency_check" | "rebuild") => void;
  onRefresh: () => void;
}) {
  const latest = jobs[0] ?? null;
  const active = latest?.status === "queued" || latest?.status === "running";
  const expected = latest?.result.expected_counts as Record<string, number> | undefined;
  const actual = latest?.result.actual_counts as Record<string, number> | undefined;
  return (
    <section className="projection-maintenance" aria-labelledby="projection-maintenance-title">
      <header>
        <span>
          <Database size={17} />
          <strong id="projection-maintenance-title">检索投影维护</strong>
        </span>
        <div>
          <button className="icon-button" type="button" title="刷新投影任务" onClick={onRefresh}>
            <RotateCcw size={15} />
          </button>
          <button type="button" disabled={busy || active} onClick={() => onRequest("consistency_check")}>
            一致性检查
          </button>
          <button
            className="danger-button"
            type="button"
            disabled={busy || active}
            onClick={() => onRequest("rebuild")}
          >
            原子重建全局投影
          </button>
        </div>
      </header>
      {loading ? <Spinner label="正在读取投影维护任务" /> : null}
      {latest ? (
        <div className="projection-maintenance-result">
          <span>
            <StatusBadge value={latest.status} />
            <strong>{latest.operation === "consistency_check" ? "一致性检查" : "全局原子重建"}</strong>
            <small>{formatDate(latest.created_at, true)}</small>
          </span>
          {expected && actual ? (
            <dl>
              {Object.keys(expected).map((kind) => (
                <div key={kind}>
                  <dt>{kind}</dt>
                  <dd>
                    {actual[kind] ?? 0} / {expected[kind] ?? 0}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {latest.last_error ? <p>{latest.last_error}</p> : null}
        </div>
      ) : (
        <p className="field-help">尚无投影维护任务。</p>
      )}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

const IDENTITY_DECISION_LABELS: Record<string, string> = {
  approve: "批准合并",
  reject: "保持独立",
  revert: "拆分恢复",
};

function IdentityImpactPanel({ impact }: { impact: EntityResolutionImpact }) {
  return (
    <section className="identity-impact" aria-labelledby="identity-impact-title">
      <header>
        <div>
          <h3 id="identity-impact-title">跨域影响分析</h3>
          <p>统计当前租户所有已声明 `entities.id` 外键，不修改任何领域记录。</p>
        </div>
        <StatusBadge value={impact.rollback_available ? "rollback ready" : impact.case.status} />
      </header>
      <dl className="identity-impact-metrics">
        <div>
          <dt>来源实体引用</dt>
          <dd>{impact.source_reference_count}</dd>
        </div>
        <div>
          <dt>候选实体引用</dt>
          <dd>{impact.candidate_reference_count}</dd>
        </div>
        <div>
          <dt>来源可信标识</dt>
          <dd>{impact.source_trusted_identifier_count}</dd>
        </div>
        <div>
          <dt>候选可信标识</dt>
          <dd>{impact.candidate_trusted_identifier_count}</dd>
        </div>
      </dl>
      {impact.references.length ? (
        <div className="table-frame identity-impact-table">
          <table>
            <thead>
              <tr>
                <th>领域</th>
                <th>引用位置</th>
                <th>来源</th>
                <th>候选</th>
              </tr>
            </thead>
            <tbody>
              {impact.references.map((item) => (
                <tr key={`${item.table}:${item.column}`}>
                  <td>{item.domain}</td>
                  <td className="mono-cell">
                    {item.table}.{item.column}
                  </td>
                  <td>{item.source_count}</td>
                  <td>{item.candidate_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="field-help">两个实体当前都没有领域引用。</p>
      )}
      {impact.decisions.length ? (
        <div className="identity-decision-history">
          <h4>不可变决策历史</h4>
          <ol>
            {impact.decisions.map((decision) => (
              <li key={decision.id}>
                <span>
                  <strong>{IDENTITY_DECISION_LABELS[decision.action] ?? decision.action}</strong>
                  <small>{formatDate(decision.created_at, true)}</small>
                </span>
                <p>{decision.notes ?? "未填写说明"}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}

function GovernanceRunsPanel({
  page,
  loading,
  error,
  status,
  offset,
  selectedRunId,
  onStatus,
  onOffset,
  onSelect,
  onRetry,
}: {
  page: Awaited<ReturnType<typeof loadGovernanceRuns>> | null;
  loading: boolean;
  error: string;
  status: GovernanceRunStatus | "all";
  offset: number;
  selectedRunId: string;
  onStatus: (value: GovernanceRunStatus | "all") => void;
  onOffset: (value: number) => void;
  onSelect: (value: string) => void;
  onRetry: () => void;
}) {
  if (loading) return <Spinner label="正在读取 AI 治理运行" />;
  if (error && !page) return <ErrorState message={error} retry={onRetry} />;
  const items = page?.items ?? [];
  const selected = items.find((item) => item.id === selectedRunId) ?? items[0] ?? null;
  const limit = page?.limit ?? 30;
  return (
    <>
      <div className="governance-run-toolbar">
        <label>
          <span>运行状态</span>
          <select value={status} onChange={(event) => onStatus(event.target.value as GovernanceRunStatus | "all")}>
            <option value="all">全部</option>
            <option value="pending">等待中</option>
            <option value="running">运行中</option>
            <option value="succeeded">成功</option>
            <option value="partial">部分成功</option>
            <option value="failed">失败</option>
            <option value="canceled">已取消</option>
          </select>
        </label>
        <span>
          共 <strong>{page?.total ?? 0}</strong> 次运行
        </span>
        {page ? (
          <code title={page.current_policy_sha256}>当前策略 {page.current_policy_sha256.slice(0, 12)}</code>
        ) : null}
      </div>
      {!items.length ? (
        <EmptyState title="当前筛选下没有 AI 治理运行" />
      ) : (
        <section className="governance-layout">
          <aside className="review-list">
            <div className="review-list-head">
              <Activity size={19} />
              <span>
                <strong>{items.length}</strong> 条运行记录
              </span>
            </div>
            {items.map((run) => (
              <button
                key={run.id}
                type="button"
                className={selected?.id === run.id ? "active" : ""}
                onClick={() => onSelect(run.id)}
              >
                <div>
                  <strong>{run.source_file_name}</strong>
                  <StatusBadge value={run.status} />
                </div>
                <p>{run.model_name}</p>
                <small>
                  {run.schema_name} {run.schema_version} · {formatDate(run.created_at, true)}
                </small>
              </button>
            ))}
          </aside>
          <GovernanceRunDetail run={selected} />
        </section>
      )}
      <nav className="governance-run-pagination" aria-label="AI 治理运行分页">
        <button
          type="button"
          title="上一页"
          aria-label="AI 治理运行上一页"
          disabled={offset === 0}
          onClick={() => onOffset(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={17} />
        </button>
        <span>{page?.total ? `${offset + 1}-${Math.min(offset + limit, page.total)} / ${page.total}` : "0 / 0"}</span>
        <button
          type="button"
          title="下一页"
          aria-label="AI 治理运行下一页"
          disabled={!page || offset + limit >= page.total}
          onClick={() => onOffset(offset + limit)}
        >
          <ChevronRight size={17} />
        </button>
      </nav>
    </>
  );
}

function GovernanceRunDetail({ run }: { run: GovernanceRun | null }) {
  if (!run) return <article className="review-detail" />;
  const totalTokens = (run.input_tokens ?? 0) + (run.output_tokens ?? 0);
  return (
    <article className="review-detail">
      <header>
        <div>
          <p className="eyebrow">AI GOVERNANCE RUN</p>
          <h2>{run.source_file_name}</h2>
          <p>{run.source_logical_path}</p>
        </div>
        <StatusBadge value={run.status} />
      </header>
      <section>
        <h3>执行配置</h3>
        <dl className="review-source governance-run-metadata">
          <div>
            <dt>模型</dt>
            <dd>
              {run.model_provider} / {run.model_name}
            </dd>
          </div>
          <div>
            <dt>Schema</dt>
            <dd>
              {run.schema_name} {run.schema_version}
            </dd>
          </div>
          <div>
            <dt>策略状态</dt>
            <dd>{run.policy_current ? "当前策略" : "历史策略"}</dd>
          </div>
          <div>
            <dt>Token / 成本</dt>
            <dd>
              {totalTokens || "未上报"}
              {run.estimated_cost ? ` / ${run.estimated_cost}` : ""}
            </dd>
          </div>
          <div>
            <dt>开始时间</dt>
            <dd>{formatDate(run.started_at ?? run.created_at, true)}</dd>
          </div>
          <div>
            <dt>完成时间</dt>
            <dd>{run.completed_at ? formatDate(run.completed_at, true) : "尚未完成"}</dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>可审计指纹</h3>
        <dl className="governance-fingerprints">
          <div>
            <dt>Source</dt>
            <dd>
              <code>{run.source_content_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Input</dt>
            <dd>
              <code>{run.input_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Prompt</dt>
            <dd>
              <code>{run.prompt_sha256}</code>
            </dd>
          </div>
          <div>
            <dt>Policy</dt>
            <dd>
              <code>{run.policy_sha256}</code>
            </dd>
          </div>
        </dl>
      </section>
      <section>
        <h3>校验结果</h3>
        {run.validation_errors.length ? (
          <pre className="json-preview compact">{JSON.stringify(run.validation_errors, null, 2)}</pre>
        ) : (
          <p className="muted">未记录结构化校验错误</p>
        )}
      </section>
    </article>
  );
}
