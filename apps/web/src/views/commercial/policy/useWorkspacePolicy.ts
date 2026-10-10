import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  type CollectionPolicy,
  type CollectionPolicyDraft,
  collectionsKeys,
  getWorkspaceExportPolicy,
} from "../../../lib/contracts/collections";
import type { CommercialOperationBoundary } from "../useCommercialOperationBoundary";
import { defaultPolicyDraft } from "./workspacePolicyFields";
export function useWorkspacePolicyDrafts() {
  const [draft, setDraft] = useState<CollectionPolicyDraft>(defaultPolicyDraft);
  const initialized = useRef(false);
  return { draft, setDraft, initialized };
}
export type WorkspacePolicyDrafts = ReturnType<typeof useWorkspacePolicyDrafts>;
export function useWorkspacePolicy(boundary: CommercialOperationBoundary, store: WorkspacePolicyDrafts) {
  const client = useQueryClient(),
    mounted = useRef(true);
  const [savedVersion, setSavedVersion] = useState("");
  const [mismatch, setMismatch] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const query = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
  });
  useEffect(() => {
    if (!query.isSuccess || store.initialized.current) return;
    store.initialized.current = true;
    const policy = query.data;
    if (policy)
      store.setDraft({
        policy_version: policy.policy_version,
        enabled: policy.enabled,
        allowed_formats: policy.allowed_formats,
        allowed_fields: policy.allowed_fields,
        max_records_per_export: policy.max_records_per_export,
        attribution: policy.attribution,
      });
  }, [query.data, query.isSuccess, store.initialized, store.setDraft]);
  function update(next: CollectionPolicyDraft) {
    if (boundary.isLocked()) return;
    store.setDraft(next);
    setSavedVersion("");
    setMismatch(false);
  }
  async function save() {
    if (!query.isSuccess || query.error || query.isFetching || boundary.isLocked()) return;
    const intent = store.draft;
    setSavedVersion("");
    setMismatch(false);
    const policy = await boundary.runWorkspacePolicy(intent);
    if (!policy || !mounted.current) return;
    if (policy.policy_version !== intent.policy_version) {
      setMismatch(true);
      return;
    }
    client.setQueryData<CollectionPolicy | null>(collectionsKeys.policy, policy);
    setSavedVersion(policy.policy_version);
  }
  return {
    query,
    draft: store.draft,
    update,
    save,
    savedVersion,
    mismatch,
    busy: Boolean(boundary.busy),
    error: boundary.actionError,
  };
}
