import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { actOnDataQualityIssue, evaluateDataQuality, governanceKeys } from "../../lib/contracts/governance";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import type { GovernanceActivity } from "../../views/governance/useGovernanceActivity";
import { useSessionIdentity } from "../SessionIdentityContext";
import type { QualityDraft, QualityDraftState } from "./useQualityDrafts";
import { qualityReadCurrent, useQualityReads } from "./useQualityReads";

export const ACTIVE_QUALITY_STATUSES = new Set(["open", "acknowledged", "ready_to_resolve"]);
type IssueAction = "assign" | "acknowledge" | "resolve" | "waive";

/** Immutable issue/version intent and issue-bound drafts share the workspace's single operation boundary. */
export function useQualityOperations(activity: GovernanceActivity, ready: boolean, draftState: QualityDraftState) {
  const actor = useSessionIdentity();
  const client = useQueryClient();
  const { status, setStatus, selectedId, setSelectedId, drafts, setDrafts } = draftState;
  const [validation, setValidation] = useState<"mismatch" | null>(null);
  const [submitted, setSubmitted] = useState<"action" | "evaluation" | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const reads = useQualityReads(status, selectedId);
  const issue = reads.selectedIssue;
  const draft = issue && Object.hasOwn(drafts, issue.id) ? drafts[issue.id] : {};
  const ownerId = draft.ownerId ?? issue?.owner_user_id ?? "";
  const notes = draft.notes ?? "";
  const canReview = Boolean(actor && ["admin", "analyst"].includes(actor.role));
  const issueCurrent = ready && canReview && qualityReadCurrent(reads.issues);
  const historyCurrent = Boolean(issue && qualityReadCurrent(reads.events));
  const canAct = Boolean(
    issue && !validation && ACTIVE_QUALITY_STATUSES.has(issue.status) && issueCurrent && historyCurrent,
  );
  const ownerCurrent = qualityReadCurrent(reads.owners);
  const canAssign = canAct && ownerCurrent && Boolean(reads.ownerData?.some((owner) => owner.id === ownerId));
  const canAcknowledge = canAct && issue?.status === "open" && Boolean(issue.owner_user_id);
  const canResolve =
    canAct &&
    issue?.status === "ready_to_resolve" &&
    Boolean(actor?.role === "admin" || (actor && issue.owner_user_id === actor.id)) &&
    Boolean(notes.trim());
  const canWaive = canAct && actor?.role === "admin" && Boolean(notes.trim());
  const canEvaluate =
    ready &&
    canReview &&
    qualityReadCurrent(reads.snapshots) &&
    qualityReadCurrent(reads.coverage) &&
    qualityReadCurrent(reads.issues);
  const evaluation = useMutation({
    mutationFn: evaluateDataQuality,
    onSuccess: async () => {
      if (mounted.current && activity.isCurrent()) setSubmitted("evaluation");
      await Promise.all([
        client.invalidateQueries({ queryKey: governanceKeys.qualitySnapshots }),
        client.invalidateQueries({ queryKey: governanceKeys.qualityCoverage }),
        client.invalidateQueries({ queryKey: ["governance", "quality-issues"] }),
      ]);
    },
    onSettled: () => activity.release(),
  });
  const action = useMutation({
    mutationFn: actOnDataQualityIssue,
    onSuccess: async (result, request) => {
      if (result.id !== request.issueId || result.version <= request.expected_version) {
        if (mounted.current && activity.isCurrent()) setValidation("mismatch");
      } else if (mounted.current && activity.isCurrent()) {
        setDrafts((current) => ({
          ...current,
          [request.issueId]: { ...current[request.issueId], notes: "", ownerId: result.owner_user_id ?? "" },
        }));
        setSubmitted("action");
      }
      await Promise.all([
        client.invalidateQueries({ queryKey: ["governance", "quality-issues"] }),
        client.invalidateQueries({ queryKey: governanceKeys.qualityIssueEvents(request.issueId) }),
      ]);
    },
    onSettled: () => activity.release(),
  });
  function updateDraft(next: QualityDraft) {
    if (!issue || activity.isLocked()) return;
    setDrafts((current) => ({ ...current, [issue.id]: { ...current[issue.id], ...next } }));
  }
  function select(id: string) {
    if (activity.isLocked()) return;
    setSelectedId(id);
    setValidation(null);
    setSubmitted(null);
    action.reset();
  }
  function filter(next: string) {
    if (activity.isLocked()) return;
    setStatus(next);
    setSelectedId("");
    setValidation(null);
    setSubmitted(null);
    action.reset();
  }
  function submit(requested: IssueAction) {
    const permitted = { assign: canAssign, acknowledge: canAcknowledge, resolve: canResolve, waive: canWaive };
    if (!issue || !permitted[requested] || !activity.acquire("quality-action")) return;
    setValidation(null);
    setSubmitted(null);
    action.mutate({
      issueId: issue.id,
      action: requested,
      expected_version: issue.version,
      owner_user_id: requested === "assign" ? ownerId : null,
      notes: notes.trim() || null,
    });
  }
  function evaluate() {
    if (!canEvaluate || !activity.acquire("quality-evaluation")) return;
    setValidation(null);
    setSubmitted(null);
    evaluation.mutate();
  }
  async function refreshIssues() {
    if (activity.isLocked()) return;
    const results = await Promise.all([reads.issues.refetch(), reads.owners.refetch(), reads.events.refetch()]);
    if (
      mounted.current &&
      activity.isCurrent() &&
      !activity.isLocked() &&
      results.every((result) => result.isSuccess)
    ) {
      setValidation(null);
    }
  }
  return {
    ...reads,
    actor,
    status,
    issue,
    ownerId,
    notes,
    busy: activity.busy,
    intent: activity.intent,
    canReview,
    canAct,
    canAssign,
    canAcknowledge,
    canResolve,
    canWaive,
    canEvaluate,
    ownerCurrent,
    submitted,
    evaluation,
    action,
    select,
    filter,
    updateDraft,
    submit,
    evaluate,
    refreshIssues,
    validation: validation ? t("提交结果与原事件不一致；请刷新权威记录后再操作。") : "",
  };
}
export type QualityOperations = ReturnType<typeof useQualityOperations>;
