import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  type CollectionPolicy,
  type CollectionPolicyDraft,
  collectionsKeys,
  getWorkspaceExportPolicy,
} from "../../../lib/contracts/collections";
import type { CommercialOperationBoundary } from "../useCommercialOperationBoundary";
import { hasPolicyEdits, policyDraft, policyIdentity, type WorkspacePolicyState } from "./policyDraftState";
import { defaultPolicyDraft } from "./workspacePolicyFields";
export function useWorkspacePolicyDrafts() {
  const [state, setState] = useState<WorkspacePolicyState>(() => ({ draft: defaultPolicyDraft(), origin: undefined }));
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
  return { state, setState, expandedGroups, setExpandedGroups };
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
  const busy = Boolean(boundary.busy);
  useEffect(() => {
    if (!query.isSuccess || busy) return;
    const policy = query.data ?? null;
    store.setState((current) => {
      if (
        current.origin !== undefined &&
        (hasPolicyEdits(current) || policyIdentity(current.origin) === policyIdentity(policy))
      )
        return current;
      return { draft: policyDraft(policy), origin: policy };
    });
  }, [query.data, query.isSuccess, busy, store.setState]);
  const conflict =
    query.isSuccess &&
    store.state.origin !== undefined &&
    hasPolicyEdits(store.state) &&
    policyIdentity(store.state.origin) !== policyIdentity(query.data);
  function update(next: CollectionPolicyDraft) {
    if (boundary.isLocked()) return;
    store.setState((current) => ({ ...current, draft: next }));
    setSavedVersion("");
    setMismatch(false);
  }
  async function save() {
    if (!query.isSuccess || query.error || query.isFetching || boundary.isLocked() || conflict) return;
    const intent = {
      ...store.state.draft,
      allowed_formats: [...store.state.draft.allowed_formats],
      allowed_fields: [...store.state.draft.allowed_fields],
    };
    setSavedVersion("");
    setMismatch(false);
    const policy = await boundary.runWorkspacePolicy(intent);
    if (!policy || !mounted.current) return;
    if (policy.policy_version !== intent.policy_version) {
      setMismatch(true);
      return;
    }
    store.setState({ draft: policyDraft(policy), origin: policy });
    client.setQueryData<CollectionPolicy | null>(collectionsKeys.policy, policy);
    setSavedVersion(policy.policy_version);
  }
  return {
    query,
    draft: store.state.draft,
    update,
    save,
    savedVersion,
    mismatch,
    conflict,
    useLatest: () => {
      if (!query.isSuccess || query.isFetching || boundary.isLocked()) return;
      store.setState({ draft: policyDraft(query.data ?? null), origin: query.data ?? null });
      setSavedVersion("");
      setMismatch(false);
    },
    busy,
    error: boundary.actionError,
  };
}
