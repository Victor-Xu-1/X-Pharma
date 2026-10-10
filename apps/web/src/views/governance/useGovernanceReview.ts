import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  decideEntityResolution,
  decideStagedFact,
  governanceKeys,
  loadEntityResolutionHistory,
  loadEntityResolutionImpact,
  loadFactComparison,
  loadGovernanceQueues,
} from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import { type governanceReviewMessages, governanceReviewText as t } from "../../lib/i18n/governanceReview";
import { governanceReadDenied } from "./governanceQueryState";

export type GovernanceMode = "facts" | "identity" | "quality" | "runs";
export type IdentityScope = "pending" | "history";
type Message = keyof typeof governanceReviewMessages;
type Feedback = { kind: "interface"; key: Message } | { kind: "raw"; message: string };

/** Owns selection, record-bound drafts and one immutable in-flight review intent. */
export function useGovernanceReview() {
  useLocale();
  const [mode, setMode] = useState<GovernanceMode>("facts");
  const [identityScope, setIdentityScope] = useState<IdentityScope>("pending");
  const [selectedFactId, setSelectedFactId] = useState("");
  const [selectedIdentityId, setSelectedIdentityId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [canonicalChoices, setCanonicalChoices] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<Feedback | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const queues = useQuery({
    queryKey: governanceKeys.queues,
    queryFn: ({ signal }) => loadGovernanceQueues(signal),
  });
  const identityHistory = useQuery({
    queryKey: governanceKeys.identityHistory,
    queryFn: ({ signal }) => loadEntityResolutionHistory(signal),
    enabled: mode === "identity",
  });
  const data = governanceReadDenied(queues.error) ? undefined : queues.data;
  const facts = data?.facts ?? [];
  const identityCases = data?.identityCases ?? [];
  const history = governanceReadDenied(identityHistory.error) ? undefined : identityHistory.data;
  const visibleIdentityCases = identityScope === "pending" ? identityCases : (history ?? []);
  const selected = facts.find((item) => item.id === selectedFactId) ?? facts[0] ?? null;
  const factComparison = useQuery({
    queryKey: governanceKeys.factComparison(selected?.id ?? "none"),
    queryFn: ({ signal }) => loadFactComparison(selected?.id ?? "", signal),
    enabled: mode === "facts" && Boolean(selected),
  });
  const selectedIdentity =
    visibleIdentityCases.find((item) => item.id === selectedIdentityId) ?? visibleIdentityCases[0] ?? null;
  const identityImpact = useQuery({
    queryKey: governanceKeys.identityImpact(selectedIdentity?.id ?? "none"),
    queryFn: ({ signal }) => loadEntityResolutionImpact(selectedIdentity?.id ?? "", signal),
    enabled: mode === "identity" && Boolean(selectedIdentity),
  });
  const impactMatches = Boolean(
    selectedIdentity &&
      identityImpact.data &&
      identityImpact.data.case.id === selectedIdentity.id &&
      identityImpact.data.case.source_entity_id === selectedIdentity.source_entity_id &&
      identityImpact.data.case.candidate_entity_id === selectedIdentity.candidate_entity_id &&
      identityImpact.data.case.status === selectedIdentity.status,
  );
  const impact = impactMatches && !governanceReadDenied(identityImpact.error) ? identityImpact.data : undefined;
  const impactError =
    identityImpact.error instanceof Error
      ? identityImpact.error.message
      : identityImpact.data && !impactMatches
        ? t("实体影响记录与当前审核对象不匹配")
        : "";
  const recommended = impact?.recommended_canonical_entity_id ?? "";
  const options = selectedIdentity ? [selectedIdentity.source_entity_id, selectedIdentity.candidate_entity_id] : [];
  const chosen = selectedIdentity ? canonicalChoices[selectedIdentity.id] : "";
  const canonicalEntityId = options.includes(chosen) ? chosen : options.includes(recommended) ? recommended : "";
  const draftKey = mode === "identity" ? `identity:${selectedIdentity?.id ?? ""}` : `fact:${selected?.id ?? ""}`;
  const notes = Object.hasOwn(drafts, draftKey) ? drafts[draftKey] : "";
  const queueReady = Boolean(data && !queues.error && !queues.isFetching);
  const factReady = Boolean(
    queueReady &&
      selected &&
      !factComparison.error &&
      !factComparison.isFetching &&
      factComparison.data?.fact.id === selected.id &&
      factComparison.data.fact.status === selected.status,
  );
  const identityReady = Boolean(
    queueReady &&
      selectedIdentity &&
      impact &&
      !impactError &&
      !identityImpact.isFetching &&
      (identityScope === "pending" || (!identityHistory.error && !identityHistory.isFetching)),
  );
  const factDecision = useMutation({ mutationFn: decideStagedFact });
  const identityDecision = useMutation({ mutationFn: decideEntityResolution });
  const error = failure ? (failure.kind === "raw" ? failure.message : t(failure.key)) : "";
  function clearFeedback() {
    setFailure(null);
    setSubmitted(false);
  }
  function changeMode(next: GovernanceMode) {
    if (locked.current) return;
    setMode(next);
    clearFeedback();
  }
  function changeIdentityScope(next: IdentityScope) {
    if (locked.current) return;
    setIdentityScope(next);
    setSelectedIdentityId("");
    clearFeedback();
  }
  function selectFact(id: string) {
    if (locked.current) return;
    setSelectedFactId(id);
    clearFeedback();
  }
  function selectIdentity(id: string) {
    if (locked.current) return;
    setSelectedIdentityId(id);
    clearFeedback();
  }
  function setNotes(value: string) {
    if (!locked.current) setDrafts((previous) => ({ ...previous, [draftKey]: value }));
  }
  function setCanonicalEntityId(value: string) {
    if (!locked.current && selectedIdentity && options.includes(value))
      setCanonicalChoices((previous) => ({ ...previous, [selectedIdentity.id]: value }));
  }
  async function execute(work: () => Promise<unknown>, refresh: () => Promise<unknown>) {
    if (locked.current || !mounted.current) return;
    locked.current = true;
    setBusy(true);
    clearFeedback();
    const submittedKey = draftKey;
    try {
      await work();
      if (!mounted.current) return;
      setDrafts((previous) => ({ ...previous, [submittedKey]: "" }));
      setSubmitted(true);
      await refresh();
    } catch (caught) {
      if (mounted.current)
        setFailure(
          caught instanceof Error
            ? { kind: "raw", message: caught.message }
            : { kind: "interface", key: "审核操作失败" },
        );
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function decide(decision: "approve" | "reject") {
    if (!selected || locked.current || !factReady || !["review_pending", "conflict"].includes(selected.status)) return;
    if ((decision === "reject" || selected.status === "conflict") && !notes.trim()) {
      setFailure({
        kind: "interface",
        key: decision === "reject" ? "拒绝时必须填写原因" : "冲突事实批准前必须填写审核意见",
      });
      return;
    }
    const request = { stagedFactId: selected.id, decision, notes };
    void execute(
      () => factDecision.mutateAsync(request),
      () => queues.refetch(),
    );
  }
  function decideIdentity(action: "approve" | "reject" | "revert") {
    if (!selectedIdentity || locked.current || !identityReady) return;
    if (
      action === "revert"
        ? selectedIdentity.status !== "approved" || !impact?.rollback_available
        : selectedIdentity.status !== "pending"
    )
      return;
    if (!notes.trim()) {
      setFailure({
        kind: "interface",
        key:
          action === "reject"
            ? "保持实体独立时必须填写原因"
            : action === "revert"
              ? "拆分恢复前必须填写依据"
              : "设为同一实体时必须填写审核依据",
      });
      return;
    }
    if (action === "approve" && !canonicalEntityId) {
      setFailure({ kind: "interface", key: "必须选择保留的规范实体" });
      return;
    }
    const request = {
      caseId: selectedIdentity.id,
      action,
      expectedStatus: selectedIdentity.status,
      canonicalEntityId: action === "approve" ? canonicalEntityId : null,
      notes,
    };
    void execute(
      () => identityDecision.mutateAsync(request),
      () => Promise.all([queues.refetch(), identityHistory.refetch(), identityImpact.refetch()]),
    );
  }
  return {
    mode,
    changeMode,
    identityScope,
    changeIdentityScope,
    queues,
    data,
    facts,
    identityCases,
    visibleIdentityCases,
    identityHistory,
    history,
    selected,
    selectedIdentity,
    selectFact,
    selectIdentity,
    identityImpact,
    impact,
    impactError,
    canonicalEntityId,
    setCanonicalEntityId,
    notes,
    setNotes,
    busy,
    error,
    submitted,
    queueReady,
    factReady,
    factComparison,
    identityReady,
    decide,
    decideIdentity,
  };
}
export type GovernanceReviewController = ReturnType<typeof useGovernanceReview>;
