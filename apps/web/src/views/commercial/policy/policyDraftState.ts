import type { CollectionPolicy, CollectionPolicyDraft } from "../../../lib/contracts/collections";
import { defaultPolicyDraft } from "./workspacePolicyFields";

export type WorkspacePolicyState = {
  draft: CollectionPolicyDraft;
  origin: CollectionPolicy | null | undefined;
};
export function policyDraft(policy: CollectionPolicy | null): CollectionPolicyDraft {
  return policy
    ? {
        policy_version: policy.policy_version,
        enabled: policy.enabled,
        allowed_formats: [...policy.allowed_formats],
        allowed_fields: [...policy.allowed_fields],
        max_records_per_export: policy.max_records_per_export,
        attribution: policy.attribution,
      }
    : defaultPolicyDraft();
}
export function samePolicyDraft(a: CollectionPolicyDraft, b: CollectionPolicyDraft) {
  return (
    JSON.stringify([
      a.policy_version,
      a.enabled,
      a.allowed_formats,
      a.allowed_fields,
      a.max_records_per_export,
      a.attribution,
    ]) ===
    JSON.stringify([
      b.policy_version,
      b.enabled,
      b.allowed_formats,
      b.allowed_fields,
      b.max_records_per_export,
      b.attribution,
    ])
  );
}
export function policyIdentity(policy: CollectionPolicy | null | undefined) {
  return policy ? JSON.stringify([policy.id, policy.policy_sha256, policy.updated_at, policyDraft(policy)]) : "absent";
}
export function hasPolicyEdits(state: WorkspacePolicyState) {
  return state.origin !== undefined && !samePolicyDraft(state.draft, policyDraft(state.origin));
}
