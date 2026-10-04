import { useMutation, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ErrorState, Spinner } from "../../components/common";
import {
  type CollectionDetail,
  collectionsKeys,
  exportComparisonSet,
  getWorkspaceExportPolicy,
} from "../../lib/contracts/collections";
import { downloadBlob, type ExportFormat } from "../../lib/download";

const requiredFields = new Set(["id", "entity_type", "name"]);
const fieldLabels: Record<string, string> = {
  position: "序号",
  id: "记录编号",
  entity_type: "类型",
  name: "名称",
  description: "描述",
  external_ids: "外部标识",
  created_at: "创建时间",
  updated_at: "更新时间",
};

export function CollectionExport({ detail, changing }: { detail: CollectionDetail; changing: boolean }) {
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
  });
  const policy = policyQuery.data;
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [fields, setFields] = useState<string[]>(["position", "id", "entity_type", "name"]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const live = useRef(true);
  const lock = useRef(false);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  useEffect(() => {
    if (!policy) return;
    setFormat(policy.allowed_formats[0] ?? "xlsx");
    setFields(policy.allowed_fields.filter((field) => requiredFields.has(field) || field === "position"));
  }, [policy]);
  const mutation = useMutation({
    mutationFn: () =>
      exportComparisonSet(detail.id, {
        expected_version: detail.version,
        export_format: format,
        fields,
        idempotency_key: crypto.randomUUID(),
      }),
  });
  async function exportSet() {
    if (lock.current) return;
    lock.current = true;
    setError("");
    setNotice("");
    try {
      const blob = await mutation.mutateAsync();
      if (live.current) {
        downloadBlob(blob, `comparison-${detail.id}-v${detail.version}.${format}`);
        setNotice("导出文件已生成");
      }
    } catch (caught) {
      if (live.current) setError(caught instanceof Error ? caught.message : "导出失败");
    } finally {
      lock.current = false;
    }
  }
  if (policyQuery.isPending) return <Spinner label="正在读取导出权限" />;
  if (policyQuery.error)
    return (
      <ErrorState
        message={policyQuery.error instanceof Error ? policyQuery.error.message : "导出权限读取失败"}
        retry={() => void policyQuery.refetch()}
      />
    );
  return (
    <>
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
      <div className="export-panel">
        <div>
          <strong>导出列表</strong>
          <small>{policy ? `单次最多 ${policy.max_records_per_export} 条` : "当前暂不支持导出"}</small>
        </div>
        {policy?.enabled ? (
          <>
            <select
              value={format}
              onChange={(event) => setFormat(event.target.value as ExportFormat)}
              aria-label="导出格式"
              disabled={mutation.isPending}
            >
              {policy.allowed_formats.map((value) => (
                <option key={value} value={value}>
                  {value.toUpperCase()}
                </option>
              ))}
            </select>
            <fieldset className="export-fields" aria-label="导出字段">
              {policy.allowed_fields
                .filter((field) => !field.includes(".") && field !== "review_status")
                .map((field) => (
                  <label className="check-control" key={field}>
                    <input
                      type="checkbox"
                      checked={fields.includes(field)}
                      disabled={requiredFields.has(field) || mutation.isPending}
                      onChange={(event) =>
                        setFields((current) =>
                          event.target.checked ? [...current, field] : current.filter((item) => item !== field),
                        )
                      }
                    />
                    {fieldLabels[field] ?? field}
                  </label>
                ))}
            </fieldset>
            <button
              className="primary-button"
              type="button"
              disabled={
                changing ||
                mutation.isPending ||
                !detail.member_count ||
                detail.member_count > policy.max_records_per_export
              }
              onClick={() => void exportSet()}
            >
              <Download size={16} />
              {mutation.isPending ? "生成中" : "导出"}
            </button>
            {detail.member_count > policy.max_records_per_export ? (
              <small>列表超过当前授权导出上限，请先精简成员。</small>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
