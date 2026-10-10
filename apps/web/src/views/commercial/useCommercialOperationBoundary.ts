import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { type CollectionPolicyDraft, saveWorkspaceExportPolicy } from "../../lib/contracts/collections";
import { type CommercialOperation, commercialKeys, executeCommercialOperation } from "../../lib/contracts/commercial";
import { type commercialWorkspaceMessages, commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";

type FailureKey = keyof typeof commercialWorkspaceMessages;

/** One synchronous boundary per mounted workspace, including policy writes and reconciliation. */
export function useCommercialOperationBoundary() {
  const queryClient = useQueryClient();
  const locked = useRef(false),
    mounted = useRef(true);
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState<{ raw?: string; key?: FailureKey } | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const operation = useMutation({ mutationFn: (intent: CommercialOperation) => executeCommercialOperation(intent) });
  async function runExclusive<T>(
    key: string,
    work: () => Promise<T>,
    fallback: FailureKey,
  ): Promise<{ value: T } | null> {
    if (locked.current || !mounted.current) return null;
    locked.current = true;
    setBusy(key);
    setFailure(null);
    try {
      const value = await work();
      return mounted.current ? { value } : null;
    } catch (caught) {
      if (mounted.current) setFailure(caught instanceof Error ? { raw: caught.message } : { key: fallback });
      return null;
    } finally {
      locked.current = false;
      if (mounted.current) setBusy("");
    }
  }
  async function runOperation(key: string, intent: CommercialOperation, fallback: FailureKey): Promise<boolean> {
    const result = await runExclusive(
      key,
      async () => {
        await operation.mutateAsync(intent);
        if (mounted.current)
          await queryClient.invalidateQueries({ queryKey: commercialKeys.root, refetchType: "active" });
        return true;
      },
      fallback,
    );
    return result !== null;
  }
  async function runWorkspacePolicy(draft: CollectionPolicyDraft) {
    const intent = { ...draft, allowed_fields: [...draft.allowed_fields], allowed_formats: [...draft.allowed_formats] };
    const result = await runExclusive("workspace-policy", () => saveWorkspaceExportPolicy(intent), "导出策略保存失败");
    return result?.value ?? null;
  }
  return {
    busy,
    runOperation,
    runWorkspacePolicy,
    isLocked: () => locked.current,
    setActionError: (message: string) => {
      if (!locked.current) setFailure(message ? { raw: message } : null);
    },
    actionError: failure?.key ? t(failure.key) : (failure?.raw ?? ""),
  };
}
export type CommercialOperationBoundary = ReturnType<typeof useCommercialOperationBoundary>;
