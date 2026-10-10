import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  commitPublicationBatch,
  type PublicationBatch,
  previewPublicationBatch,
  requestProjectionMaintenance,
  type StagedFact,
} from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import {
  type governancePublicationMessages,
  governancePublicationText as t,
} from "../../lib/i18n/governancePublication";
import {
  assertPublicationCommit,
  assertPublicationPreview,
  completePublicationMembership,
  PublicationResponseError,
  publicationIntentFingerprint,
} from "./publicationValidation";
import type { GovernanceActivity } from "./useGovernanceActivity";
import { usePublicationReads } from "./usePublicationReads";

type Message = keyof typeof governancePublicationMessages;
type Feedback = { kind: "interface"; key: Message } | { kind: "raw"; message: string };
export function usePublicationBatch({
  facts,
  ready,
  activity,
  onQueuesChanged,
}: {
  facts: StagedFact[];
  ready: boolean;
  activity: GovernanceActivity;
  onQueuesChanged: () => unknown;
}) {
  useLocale();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [activeId, setActiveId] = useState("");
  const [reason, setReason] = useState("");
  const [failure, setFailure] = useState<Feedback | null>(null);
  const [notice, setNotice] = useState<Message | null>(null);
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const previewIntent = useRef<{ fingerprint: string; key: string } | null>(null);
  const reads = usePublicationReads(activeId);
  const previewMutation = useMutation({ mutationFn: previewPublicationBatch });
  const commitMutation = useMutation({ mutationFn: commitPublicationBatch });
  const maintenanceMutation = useMutation({ mutationFn: requestProjectionMaintenance });
  const eligible = new Set(
    facts.filter((fact) => ["review_pending", "conflict"].includes(fact.status)).map((fact) => fact.id),
  );
  const missing = selectedIds.filter((id) => !eligible.has(id));
  const detailReady = Boolean(reads.detail && !reads.detailError && !reads.activeBatch.isFetching);
  const jobsReady = Boolean(
    reads.allowed &&
      !reads.maintenanceAccess.isFetching &&
      reads.jobs &&
      !reads.maintenanceJobs.error &&
      !reads.maintenanceJobs.isFetching,
  );
  const activeJob = reads.jobs?.some((job) => job.status === "queued" || job.status === "running") ?? false;
  const error = failure ? (failure.kind === "raw" ? failure.message : t(failure.key)) : "";
  function reject(key: Message) {
    setNotice(null);
    setFailure({ kind: "interface", key });
  }
  function changeReason(value: string) {
    if (!activity.isLocked()) setReason(value);
  }
  function select(id: string, checked: boolean) {
    if (activity.isLocked() || !ready || !eligible.has(id)) return;
    setSelectedIds((previous) =>
      checked ? [...new Set([...previous, id])] : previous.filter((value) => value !== id),
    );
  }
  function toggleAll() {
    if (activity.isLocked() || !ready) return;
    setSelectedIds(selectedIds.length === eligible.size && !missing.length ? [] : [...eligible]);
  }
  function selectBatch(id: string) {
    if (activity.isLocked()) return;
    setActiveId(id);
    setFailure(null);
    setNotice(null);
  }
  async function execute(intent: string, work: () => Promise<void>) {
    if (!activity.acquire(intent)) return;
    setFailure(null);
    setNotice(null);
    try {
      await work();
    } catch (caught) {
      if (activity.isCurrent())
        setFailure(
          caught instanceof PublicationResponseError
            ? { kind: "interface", key: caught.key }
            : caught instanceof Error
              ? { kind: "raw", message: caught.message }
              : { kind: "interface", key: "批次操作失败" },
        );
    } finally {
      activity.release();
    }
  }
  function preview(operation: PublicationBatch["operation"], ids: string[]) {
    const fingerprint = publicationIntentFingerprint(operation, ids, reason);
    if (previewIntent.current?.fingerprint !== fingerprint)
      previewIntent.current = { fingerprint, key: `governance-ui:${operation}:${globalThis.crypto.randomUUID()}` };
    const request = { operation, stagedFactIds: [...ids], reason, idempotencyKey: previewIntent.current.key };
    void execute("publication:preview", async () => {
      const result = await previewMutation.mutateAsync(request);
      assertPublicationPreview(result, request.operation, request.stagedFactIds);
      if (!activity.isCurrent()) return;
      setActiveId(result.id);
      setNotice(result.status === "committed" ? "批次操作已提交" : "固定预览已生成");
      await reads.batches.refetch();
    });
  }
  function previewPublish() {
    if (activity.isLocked() || !ready) return;
    if (!selectedIds.length) return reject("请先选择至少一项待审事实");
    if (missing.length) return reject("请刷新并重新核对已选事实");
    if (!reason.trim()) return reject("批次发布必须填写审核依据");
    preview("publish", selectedIds);
  }
  function previewWithdrawal() {
    const batch = reads.detail;
    if (activity.isLocked() || !detailReady || !batch || batch.status !== "committed" || batch.operation !== "publish")
      return;
    if (!reason.trim()) return reject("批次撤回必须填写具体依据");
    if (!completePublicationMembership(batch)) return reject("请等待批次明细加载完成");
    preview("withdraw", batch.items?.map((item) => item.staged_fact_id) ?? []);
  }
  function commit() {
    const batch = reads.detail;
    if (activity.isLocked() || !detailReady || !batch || batch.status !== "previewed" || batch.blocked_count !== 0)
      return;
    if (!completePublicationMembership(batch)) return reject("预览明细未完整返回");
    void execute("publication:commit", async () => {
      const result = await commitMutation.mutateAsync({ batchId: batch.id, previewSha256: batch.preview_sha256 });
      assertPublicationCommit(result, batch);
      if (!activity.isCurrent()) return;
      setSelectedIds([]);
      setReason("");
      setNotice("批次操作已提交");
      await Promise.all([reads.batches.refetch(), reads.activeBatch.refetch(), onQueuesChanged()]);
    });
  }
  function requestMaintenance(operation: "consistency_check" | "rebuild") {
    if (activity.isLocked() || !jobsReady || activeJob) return;
    if (operation === "rebuild") {
      setConfirmRebuild(true);
      return;
    }
    submitMaintenance(operation);
  }
  async function refreshMaintenance() {
    if (activity.isLocked()) return;
    const access = await reads.maintenanceAccess.refetch();
    if (activity.isCurrent() && !access.error && access.data === true) await reads.maintenanceJobs.refetch();
  }
  function submitMaintenance(operation: "consistency_check" | "rebuild") {
    if (activity.isLocked() || !jobsReady || activeJob) return;
    void execute("publication:maintenance", async () => {
      const job = await maintenanceMutation.mutateAsync(operation);
      if (job.operation !== operation) throw new PublicationResponseError("返回预览与本次操作不匹配");
      if (!activity.isCurrent()) return;
      setConfirmRebuild(false);
      setNotice("维护任务已受理");
      await reads.maintenanceJobs.refetch();
    });
  }
  return {
    ...reads,
    activity,
    busy: activity.busy,
    selectedIds,
    activeId,
    reason,
    missing,
    ready,
    detailReady,
    jobsReady,
    activeJob,
    error,
    notice: notice ? t(notice) : "",
    confirmRebuild,
    select,
    toggleAll,
    selectBatch,
    changeReason,
    previewPublish,
    previewWithdrawal,
    commit,
    requestMaintenance,
    refreshMaintenance,
    confirmMaintenance: () => {
      if (confirmRebuild) submitMaintenance("rebuild");
    },
    closeConfirmation: () => {
      if (!activity.isLocked()) setConfirmRebuild(false);
    },
  };
}
export type PublicationBatchController = ReturnType<typeof usePublicationBatch>;
