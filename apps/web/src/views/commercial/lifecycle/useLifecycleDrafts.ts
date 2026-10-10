import { useEffect, useRef, useState } from "react";
import type { DataRetentionPolicy, LegalHoldScope } from "../../../lib/contracts/commercial";

export type RetentionDraft = { hours: string; basis: string; geography: string; active: boolean };
type DraftRecord = {
  value: RetentionDraft;
  origin: DataRetentionPolicy | null | undefined;
  dirty: boolean;
  submitted: RetentionDraft | null;
};
function policyValue(policy: DataRetentionPolicy | undefined, hours: string): RetentionDraft {
  return policy
    ? {
        hours: String(policy.retention_seconds / 3600),
        basis: policy.legal_basis,
        geography: policy.geographic_scope.join(", "),
        active: policy.active,
      }
    : { hours, basis: "", geography: "CN", active: true };
}
function identity(policy: DataRetentionPolicy | null | undefined) {
  return policy
    ? JSON.stringify([policy.id, policy.policy_version, policy.updated_at, policyValue(policy, "")])
    : "absent";
}
function matchesPolicy(policy: DataRetentionPolicy | undefined, draft: RetentionDraft) {
  if (!policy) return false;
  const geography = draft.geography
    .split(",")
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
  return (
    policy.retention_seconds === Math.round(Number(draft.hours) * 3600) &&
    policy.legal_basis === draft.basis.trim() &&
    policy.active === draft.active &&
    JSON.stringify(policy.geographic_scope) === JSON.stringify(geography)
  );
}
function useRetentionDraft(policy: DataRetentionPolicy | undefined, ready: boolean, hours: string) {
  const [state, setState] = useState<DraftRecord>(() => ({
    value: policyValue(undefined, hours),
    origin: undefined,
    dirty: false,
    submitted: null,
  }));
  const latest = useRef({ policy, ready });
  latest.current = { policy, ready };
  useEffect(() => {
    if (!ready) return;
    setState((current) => {
      if (state.submitted && current.submitted === state.submitted && matchesPolicy(policy, state.submitted))
        return { value: policyValue(policy, hours), origin: policy ?? null, dirty: false, submitted: null };
      if (current.dirty || (current.origin !== undefined && identity(current.origin) === identity(policy)))
        return current;
      return { value: policyValue(policy, hours), origin: policy ?? null, dirty: false, submitted: null };
    });
  }, [policy, ready, hours, state.submitted]);
  return {
    ...state.value,
    dirty: state.dirty,
    conflict:
      ready &&
      state.dirty &&
      identity(state.origin) !== identity(policy) &&
      !(state.submitted && matchesPolicy(policy, state.submitted)),
    update: (patch: Partial<RetentionDraft>) =>
      setState((current) => ({ ...current, value: { ...current.value, ...patch }, dirty: true, submitted: null })),
    useLatest: () => {
      if (latest.current.ready)
        setState({
          value: policyValue(latest.current.policy, hours),
          origin: latest.current.policy ?? null,
          dirty: false,
          submitted: null,
        });
    },
    acknowledgeSaved: (submitted: RetentionDraft) => setState((current) => ({ ...current, submitted })),
  };
}
export function useLifecycleDrafts(policies: DataRetentionPolicy[], ready: boolean) {
  const exportPolicy = policies.find((policy) => policy.data_class === "commercial_export_artifact");
  const sourcePolicy = policies.find((policy) => policy.data_class === "source_asset_snapshot");
  const exportDraft = useRetentionDraft(exportPolicy, ready, "24");
  const sourceDraft = useRetentionDraft(sourcePolicy, ready, "720");
  const [hold, setHold] = useState<{
    scopeType: LegalHoldScope;
    scopeId: string;
    matterReference: string;
    reason: string;
  }>({ scopeType: "tenant", scopeId: "", matterReference: "", reason: "" });
  return {
    exportPolicy,
    sourcePolicy,
    exportDraft,
    sourceDraft,
    hold,
    updateHold: (patch: Partial<typeof hold>) => setHold((current) => ({ ...current, ...patch })),
    acknowledgeHold: () => setHold((current) => ({ ...current, matterReference: "", reason: "" })),
  };
}
export type LifecycleDraftState = ReturnType<typeof useLifecycleDrafts>;
export type RetentionDraftState = LifecycleDraftState["exportDraft"];
