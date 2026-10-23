import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import {
  type EnterpriseApiKey,
  type EnterpriseApiKeyOperation,
  type EnterpriseApiKeySecret,
  type EnterpriseLLMProviderOperation,
  type EnterpriseOperation,
  enterpriseKeys,
  executeEnterpriseApiKeyOperation,
  executeEnterpriseLLMProviderOperation,
  executeEnterpriseOperation,
} from "../../lib/contracts/enterprise";
import { type EnterpriseMessageKey, enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";
export type EnterpriseFailure = { raw: string } | { key: EnterpriseMessageKey };

/** No secret-bearing request/result is retained in generic mutation history. One mounted workspace owns the lock. */
export function useEnterpriseOperationBoundary() {
  const client = useQueryClient();
  const locked = useRef(false),
    mounted = useRef(true);
  const [busy, setBusy] = useState("");
  const [failure, setFailure] = useState<EnterpriseFailure | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function run<T>(
    key: string,
    work: () => Promise<T>,
    fallback: EnterpriseMessageKey,
    failurePolicy?: (error: unknown) => EnterpriseFailure,
  ): Promise<{ value: T } | null> {
    if (locked.current || !mounted.current) return null;
    locked.current = true;
    setBusy(key);
    setFailure(null);
    try {
      const value = await work();
      if (!mounted.current) return null;
      await client.invalidateQueries({ queryKey: enterpriseKeys.root, refetchType: "active" });
      return mounted.current ? { value } : null;
    } catch (error) {
      if (mounted.current)
        setFailure(
          failurePolicy ? failurePolicy(error) : error instanceof Error ? { raw: error.message } : { key: fallback },
        );
      return null;
    } finally {
      locked.current = false;
      if (mounted.current) setBusy("");
    }
  }
  return {
    busy,
    isLocked: () => locked.current,
    actionError: failure ? ("key" in failure ? t(failure.key) : failure.raw) : "",
    clearFailure: () => {
      if (!locked.current) setFailure(null);
    },
    failCurrentRead: () => {
      if (!locked.current) setFailure({ key: "请先恢复当前记录读取，再提交操作。" });
    },
    failStaleTarget: () => {
      if (!locked.current) setFailure({ key: "记录已变更，请重新核对当前记录后提交。" });
    },
    run,
    runOperation: async (key: string, operation: EnterpriseOperation, fallback: EnterpriseMessageKey) =>
      (await run(key, () => executeEnterpriseOperation(operation), fallback)) !== null,
    runApiKeyOperation: async (
      key: string,
      operation: EnterpriseApiKeyOperation,
      fallback: EnterpriseMessageKey,
    ): Promise<EnterpriseApiKey | EnterpriseApiKeySecret | null> =>
      (await run(key, () => executeEnterpriseApiKeyOperation(operation), fallback))?.value ?? null,
    runLlmOperation: async (key: string, operation: EnterpriseLLMProviderOperation, fallback: EnterpriseMessageKey) =>
      (await run(key, () => executeEnterpriseLLMProviderOperation(operation), fallback)) !== null,
  };
}
export type EnterpriseOperationBoundary = ReturnType<typeof useEnterpriseOperationBoundary>;
export const EnterpriseOperationContext = createContext<EnterpriseOperationBoundary | null>(null);
export const useEnterpriseOperationContext = () => useContext(EnterpriseOperationContext);
