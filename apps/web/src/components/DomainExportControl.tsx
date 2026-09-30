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

export function DomainExportControl({ dataset, totalRows }: { dataset: DomainExportDataset; totalRows: number }) {
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [fields, setFields] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
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
  const canExport = Boolean(policy?.enabled && exportLimit > 0 && licensedFields.some((field) => field.value === "id"));
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

  useEffect(() => {
    if (!policy) return;
    const nextFormat = policy.allowed_formats.find((value) => ["csv", "json", "xlsx"].includes(value));
    if (nextFormat) setFormat(nextFormat as ExportFormat);
    setFields(licensedFields.map((field) => field.value));
  }, [licensedFields, policy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
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

  if (!canExport) {
    return (
      <button
        className="domain-export-disabled"
        type="button"
        disabled
        title={policyQuery.isPending ? "正在读取导出权限" : "当前账号或数据许可未开放该领域导出"}
      >
        <LockKeyhole size={14} />
        <span>导出</span>
      </button>
    );
  }

  return (
    <details className="domain-export-menu">
      <summary>
        <Download size={14} />
        导出
      </summary>
      <form onSubmit={(event) => void submit(event)}>
        <header>
          <strong>{catalog.label}</strong>
          <small>最多 {exportLimit} 条</small>
        </header>
        <label>
          格式
          <select value={format} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
            {policy?.allowed_formats.map((value) => (
              <option value={value} key={value}>
                {value.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="domain-export-fields">
          <legend>导出字段</legend>
          {licensedFields.map((field) => (
            <label className="check-control domain-export-field" key={field.value}>
              <input
                type="checkbox"
                checked={fields.includes(field.value)}
                disabled={field.value === "id"}
                onChange={(event) =>
                  setFields((current) =>
                    event.target.checked ? [...current, field.value] : current.filter((value) => value !== field.value),
                  )
                }
              />
              {field.label}
            </label>
          ))}
        </fieldset>
        {error ? (
          <p className="inline-error" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="inline-feedback" role="status">
            {notice}
          </p>
        ) : null}
        <button className="primary-button" type="submit" disabled={mutation.isPending || !fields.includes("id")}>
          <Download size={15} />
          {mutation.isPending ? "生成中" : "下载"}
        </button>
      </form>
    </details>
  );
}
