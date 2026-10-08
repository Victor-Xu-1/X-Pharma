import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  type CollectionDetail,
  collectionsKeys,
  exportComparisonSet,
  getWorkspaceExportPolicy,
} from "../../lib/contracts/collections";
import { downloadBlob, type ExportFormat } from "../../lib/download";
import {
  collectionExportBlockReason,
  collectionExportFields,
  hasRequiredCollectionFields,
} from "./collectionExportPresentation";

type ExportRequest = Parameters<typeof exportComparisonSet>[1];

export function useCollectionExport(
  detail: CollectionDetail,
  open: boolean,
  state: { changing: boolean; refreshing: boolean; stale: boolean },
) {
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
    enabled: open,
    staleTime: 0,
  });
  const policy = policyQuery.data;
  const availableFields = useMemo(() => collectionExportFields(policy), [policy]);
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [fields, setFields] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const configured = useRef(false);
  const mounted = useRef(true);
  const lock = useRef(false);
  const intent = useRef<{ fingerprint: string; key: string } | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (!policy) return;
    const first = !configured.current;
    setFormat((current) => (first || !policy.allowed_formats.includes(current) ? policy.allowed_formats[0] : current));
    setFields((current) =>
      availableFields
        .filter((field) => field.required || (first ? field.value === "position" : current.includes(field.value)))
        .map((field) => field.value),
    );
    configured.current = true;
  }, [availableFields, policy]);
  const mutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: ExportRequest }) => exportComparisonSet(id, body),
  });
  const reading = policyQuery.isPending || policyQuery.isFetching;
  const blockReason = collectionExportBlockReason(detail, policy, state);
  const canExport = Boolean(
    open &&
      !reading &&
      !policyQuery.isError &&
      !blockReason &&
      policy?.allowed_formats.includes(format) &&
      hasRequiredCollectionFields(fields),
  );

  async function exportSet() {
    if (lock.current || !canExport || !policy) return;
    lock.current = true;
    setError("");
    setNotice("");
    const selected = availableFields.filter((field) => fields.includes(field.value)).map((field) => field.value);
    const fingerprint = JSON.stringify({
      id: detail.id,
      version: detail.version,
      format,
      fields: selected,
      policy: policy.policy_sha256,
    });
    if (intent.current?.fingerprint !== fingerprint) intent.current = { fingerprint, key: crypto.randomUUID() };
    const body: ExportRequest = {
      expected_version: detail.version,
      export_format: format,
      fields: selected,
      idempotency_key: intent.current.key,
    };
    try {
      const blob = await mutation.mutateAsync({ id: detail.id, body });
      if (mounted.current) {
        downloadBlob(blob, `comparison-${detail.id}-v${detail.version}.${format}`);
        setNotice(`列表 v${detail.version} 的导出文件已生成`);
        intent.current = null;
      }
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught.message : "导出失败");
    } finally {
      lock.current = false;
    }
  }

  function toggleField(field: string, selected: boolean) {
    setError("");
    setNotice("");
    setFields((current) => (selected ? [...current, field] : current.filter((value) => value !== field)));
  }
  function selectFormat(value: ExportFormat) {
    if (value === format) return;
    setError("");
    setNotice("");
    setFormat(value);
  }

  return {
    policyQuery,
    policy,
    reading,
    availableFields,
    format,
    setFormat: selectFormat,
    fields,
    toggleField,
    error,
    notice,
    pending: mutation.isPending,
    canExport,
    blockReason,
    exportSet,
  };
}
