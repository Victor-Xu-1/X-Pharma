import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, LockKeyhole } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { collectionsKeys, getWorkspaceExportPolicy } from "../lib/contracts/collections";
import {
  currentDomainExportQuery,
  type DomainExportDataset,
  domainExportCatalog,
  exportDomainQuery,
} from "../lib/contracts/domainExports";
import { downloadBlob, type ExportFormat } from "../lib/download";
import { useDismissibleDetails } from "../lib/useDismissibleDetails";
import { FormStatus } from "./FormStatus";

export function DomainExportControl({ dataset, totalRows }: { dataset: DomainExportDataset; totalRows: number }) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [fields, setFields] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
    enabled: open,
  });
  const policy = policyQuery.data ?? null;
  const catalog = domainExportCatalog[dataset];
  const licensedFields = useMemo(() => {
    const prefix = `${dataset}.`;
    const allowed = new Set(
      (policy?.allowed_fields ?? [])
        .filter((field) => field.startsWith(prefix))
        .map((field) => field.slice(prefix.length)),
    );
    return catalog.fields.filter((field) => allowed.has(field.value));
  }, [catalog.fields, dataset, policy?.allowed_fields]);
  const exportLimit = Math.min(totalRows, policy?.max_records_per_export ?? 0);
  const readingPolicy = policyQuery.isPending || policyQuery.isFetching;
  const policyError = policyQuery.error instanceof Error ? policyQuery.error.message : "导出策略读取失败";
  const hasRequiredField = licensedFields.some((field) => field.value === "id");
  const canExport = Boolean(
    !readingPolicy && !policyQuery.isError && policy?.enabled && exportLimit > 0 && hasRequiredField,
  );
  const policyLocked = Boolean(!policyQuery.isError && policy && (!policy.enabled || !hasRequiredField));
  const unavailableReason =
    totalRows <= 0
      ? "当前查询没有可导出结果；调整查询条件后再导出。"
      : !policy
        ? "本组织尚未配置导出策略；请联系管理员。"
        : !policy.enabled
          ? "本组织导出策略尚未开放该领域导出。"
          : !hasRequiredField
            ? "本组织导出策略未授权该领域的必需字段（稳定 ID）。"
            : "本组织导出策略的记录上限为 0，暂时无法导出。";
  const mutation = useMutation({
    mutationFn: () =>
      exportDomainQuery({
        dataset,
        query: currentDomainExportQuery(dataset),
        export_format: format,
        fields,
        max_records: exportLimit,
        idempotency_key: crypto.randomUUID(),
      }),
  });
  const popover = useDismissibleDetails({ dismissible: !mutation.isPending });

  useEffect(() => {
    if (!policy) return;
    const nextFormat = policy.allowed_formats.find((value) => ["csv", "json", "xlsx"].includes(value));
    if (nextFormat) setFormat(nextFormat as ExportFormat);
    setFields(licensedFields.map((field) => field.value));
  }, [licensedFields, policy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canExport || mutation.isPending || !fields.includes("id")) return;
    setError("");
    setNotice("");
    try {
      const blob = await mutation.mutateAsync();
      downloadBlob(blob, `${dataset}-query.${format}`);
      setNotice(`已导出 ${Math.min(exportLimit, totalRows)} 条以内的授权结果`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "导出失败");
    }
  }

  return (
    <details className="domain-export-menu" {...popover} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary aria-disabled={mutation.isPending || undefined}>
        {policyLocked ? <LockKeyhole size={14} aria-hidden="true" /> : <Download size={14} aria-hidden="true" />}
        导出
      </summary>
      {open ? (
        <form onSubmit={(event) => void submit(event)}>
          <header>
            <strong>{catalog.label}</strong>
            {canExport || mutation.isPending ? <small>最多 {exportLimit} 条</small> : null}
          </header>
          {readingPolicy && !mutation.isPending ? (
            <FormStatus pending pendingLabel="正在读取导出策略" />
          ) : policyQuery.isError && !mutation.isPending ? (
            <>
              <FormStatus pending={false} error={policyError} />
              <button className="secondary-button" type="button" onClick={() => void policyQuery.refetch()}>
                重新读取导出策略
              </button>
            </>
          ) : !canExport && !mutation.isPending ? (
            <p className="field-help" role="status">
              {unavailableReason}
            </p>
          ) : (
            <>
              <label>
                格式
                <select
                  value={format}
                  disabled={mutation.isPending}
                  onChange={(event) => setFormat(event.target.value as ExportFormat)}
                >
                  {policy?.allowed_formats.map((value) => (
                    <option value={value} key={value}>
                      {value.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="domain-export-fields" disabled={mutation.isPending}>
                <legend>导出字段</legend>
                {licensedFields.map((field) => (
                  <label className="check-control domain-export-field" key={field.value}>
                    <input
                      type="checkbox"
                      checked={fields.includes(field.value)}
                      disabled={field.value === "id"}
                      onChange={(event) =>
                        setFields((current) =>
                          event.target.checked
                            ? [...current, field.value]
                            : current.filter((value) => value !== field.value),
                        )
                      }
                    />
                    {field.label}
                  </label>
                ))}
              </fieldset>
              <FormStatus pending={mutation.isPending} error={error} pendingLabel="正在生成受控导出文件" />
              {notice ? (
                <p className="inline-feedback" role="status">
                  {notice}
                </p>
              ) : null}
              <button className="primary-button" type="submit" disabled={mutation.isPending || !fields.includes("id")}>
                <Download size={15} />
                {mutation.isPending ? "生成中" : "下载"}
              </button>
            </>
          )}
        </form>
      ) : null}
    </details>
  );
}
