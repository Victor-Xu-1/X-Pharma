import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ClipboardCheck, RotateCcw } from "lucide-react";
import { useState } from "react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import {
  commitPublicationBatch,
  governanceKeys,
  loadProjectionMaintenanceAccess,
  loadProjectionMaintenanceJobs,
  loadPublicationBatch,
  loadPublicationBatches,
  type PublicationBatch,
  previewPublicationBatch,
  requestProjectionMaintenance,
  type StagedFact,
} from "../../lib/contracts/governance";
import { reviewFactTitle } from "../../lib/governancePresentation";
import { useLocale } from "../../lib/i18n";
import { governancePublicationMessages, governancePublicationText as t } from "../../lib/i18n/governancePublication";
import { ProjectionMaintenancePanel } from "./ProjectionMaintenancePanel";

export function PublicationBatchPanel({
  facts,
  onQueuesChanged,
}: {
  facts: StagedFact[];
  onQueuesChanged: () => void;
}) {
  useLocale();
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
    (Object.hasOwn(governancePublicationMessages, localError)
      ? t(localError as keyof typeof governancePublicationMessages)
      : localError) ||
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
          {t("批次发布与撤回")}
        </span>
        <small>{batches.data ? t("{count} 个治理批次", { count: batches.data.length }) : ""}</small>
      </summary>
      <div className="publication-control-body">
        <section className="publication-selection" aria-labelledby="publication-selection-title">
          <header>
            <div>
              <h3 id="publication-selection-title">{t("待审事实选择")}</h3>
              <p>{t("先生成固定预览，再按同一 preview hash 原子提交。")}</p>
            </div>
            <button
              type="button"
              className="text-button"
              disabled={!facts.length}
              onClick={() =>
                setSelectedFactIds(selectedFactIds.length === facts.length ? [] : facts.map((fact) => fact.id))
              }
            >
              {t(selectedFactIds.length === facts.length && facts.length ? "取消全选" : "全选")}
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
                    <strong>{reviewFactTitle(fact)}</strong>
                    <small>{fact.source_quote}</small>
                  </span>
                  <StatusBadge value={fact.status} />
                </label>
              ))}
            </div>
          ) : (
            <p className="field-help">{t("当前没有可加入发布批次的待审事实")}</p>
          )}
          <label className="publication-reason">
            <span>{t("批次审核依据")}</span>
            <textarea
              aria-label={t("批次审核依据")}
              rows={3}
              maxLength={4000}
              value={batchReason}
              onChange={(event) => setBatchReason(event.target.value)}
            />
          </label>
          <button className="primary-button" type="button" disabled={busy} onClick={previewPublish}>
            <ClipboardCheck size={16} />
            {t("生成发布预览 ({count})", { count: selectedFactIds.length })}
          </button>
        </section>
        <section className="publication-history" aria-labelledby="publication-history-title">
          <header>
            <h3 id="publication-history-title">{t("批次历史")}</h3>
            <button
              className="icon-button"
              type="button"
              title={t("刷新批次历史")}
              aria-label={t("刷新批次历史")}
              onClick={() => void batches.refetch()}
            >
              <RotateCcw size={15} />
            </button>
          </header>
          {batches.isPending ? <Spinner label={t("正在读取发布批次")} /> : null}
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
                  <strong>{t(batch.operation === "publish" ? "发布" : "撤回")}</strong>
                  <StatusBadge value={batch.status} />
                </span>
                <small>
                  {t("{count} 项", { count: batch.expected_count })} · {formatDate(batch.created_at, true)}
                </small>
              </button>
            ))}
          </div>
        </section>
        <section className="publication-preview" aria-labelledby="publication-preview-title">
          <h3 id="publication-preview-title">{t("固定预览")}</h3>
          {activeBatch.isFetching ? <Spinner label={t("正在读取批次明细")} /> : null}
          {activeBatch.error instanceof Error ? (
            <ErrorState message={activeBatch.error.message} retry={() => void activeBatch.refetch()} />
          ) : null}
          {selectedBatch ? (
            <>
              <dl>
                <div>
                  <dt>{t("操作")}</dt>
                  <dd>{t(selectedBatch.operation === "publish" ? "批次发布" : "批次撤回")}</dd>
                </div>
                <div>
                  <dt>{t("状态")}</dt>
                  <dd>
                    <StatusBadge value={selectedBatch.status} />
                  </dd>
                </div>
                <div>
                  <dt>{t("阻塞项")}</dt>
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
                  {t(selectedBatch.operation === "publish" ? "原子提交发布" : "原子提交撤回")}
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
                  {t("基于此批次生成撤回预览")}
                </button>
              ) : null}
            </>
          ) : (
            <p className="field-help">{t("选择历史批次或生成新预览以查看逐项结果")}</p>
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
