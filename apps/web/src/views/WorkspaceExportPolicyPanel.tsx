import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";

import { ErrorState, Spinner } from "../components/common";
import {
  type CollectionPolicy,
  type CollectionPolicyDraft,
  collectionsKeys,
  getWorkspaceExportPolicy,
  saveWorkspaceExportPolicy,
} from "../lib/contracts/collections";
import { defaultWorkspacePolicyFields, domainExportCatalog } from "../lib/contracts/domainExports";

const comparisonFieldLabels: Record<string, string> = {
  position: "序号",
  id: "稳定 ID",
  entity_type: "实体类型",
  name: "名称",
  description: "描述",
  external_ids: "外部标识",
  review_status: "审核状态",
  created_at: "创建时间",
  updated_at: "更新时间",
};
const domainPolicyFieldLabels = Object.fromEntries(
  Object.entries(domainExportCatalog).flatMap(([dataset, config]) =>
    config.fields.map((field) => [`${dataset}.${field.value}`, `${config.label} · ${field.label}`]),
  ),
);
const fieldLabels: Record<string, string> = { ...comparisonFieldLabels, ...domainPolicyFieldLabels };
const requiredFields = new Set(["id", "entity_type", "name"]);
const defaultPolicyFields = [...Object.keys(comparisonFieldLabels), ...defaultWorkspacePolicyFields];

function defaultDraft(): CollectionPolicyDraft {
  return {
    policy_version: "workspace-export-v1",
    enabled: false,
    allowed_formats: ["csv", "json", "xlsx"],
    allowed_fields: [...defaultPolicyFields],
    max_records_per_export: 20,
    attribution: "Licensed for internal enterprise use",
  };
}

export function WorkspaceExportPolicyPanel() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CollectionPolicyDraft>(defaultDraft);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const policyQuery = useQuery({
    queryKey: collectionsKeys.policy,
    queryFn: ({ signal }) => getWorkspaceExportPolicy(signal),
  });
  const saveMutation = useMutation({ mutationFn: saveWorkspaceExportPolicy });

  useEffect(() => {
    const policy = policyQuery.data;
    if (!policy) return;
    setDraft({
      policy_version: policy.policy_version,
      enabled: policy.enabled,
      allowed_formats: policy.allowed_formats,
      allowed_fields: policy.allowed_fields,
      max_records_per_export: policy.max_records_per_export,
      attribution: policy.attribution,
    });
  }, [policyQuery.data]);

  async function savePolicy(event: FormEvent) {
    event.preventDefault();
    setActionError("");
    setNotice("");
    try {
      const policy = await saveMutation.mutateAsync(draft);
      queryClient.setQueryData<CollectionPolicy | null>(collectionsKeys.policy, policy);
      setNotice(`导出策略 ${policy.policy_version} 已生效`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "导出策略保存失败");
    }
  }

  if (policyQuery.isPending) return <Spinner label="正在加载工作台导出策略" />;
  if (policyQuery.error) {
    return (
      <ErrorState
        message={policyQuery.error instanceof Error ? policyQuery.error.message : "工作台导出策略加载失败"}
        retry={() => void policyQuery.refetch()}
      />
    );
  }

  return (
    <section className="export-policy-admin" aria-labelledby="workspace-export-policy-title">
      <div className="section-toolbar">
        <span>
          <strong id="workspace-export-policy-title">工作台导出策略</strong>
          <small>控制外部用户工作台可导出的格式、字段、单次上限和授权标注</small>
        </span>
      </div>
      {actionError ? (
        <p className="inline-error" role="alert">
          {actionError}
        </p>
      ) : null}
      {notice ? (
        <p className="inline-feedback" role="status">
          {notice}
        </p>
      ) : null}
      <form className="policy-form" onSubmit={(event) => void savePolicy(event)}>
        <header>
          <div>
            <strong>{policyQuery.data ? `当前版本 ${policyQuery.data.policy_version}` : "尚未配置导出策略"}</strong>
            <small>策略变更必须使用新版本号，历史导出事件保持不可修改</small>
          </div>
          <label className="check-control">
            <input
              type="checkbox"
              checked={draft.enabled}
              onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))}
            />
            启用外部工作台人工导出
          </label>
        </header>
        <fieldset className="policy-options">
          <legend>允许格式</legend>
          {(["csv", "json", "xlsx"] as const).map((format) => (
            <label className="check-control" key={format}>
              <input
                type="checkbox"
                checked={draft.allowed_formats.includes(format)}
                disabled={draft.allowed_formats.length === 1 && draft.allowed_formats.includes(format)}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    allowed_formats: event.target.checked
                      ? [...current.allowed_formats, format]
                      : current.allowed_formats.filter((item) => item !== format),
                  }))
                }
              />
              {format.toUpperCase()}
            </label>
          ))}
        </fieldset>
        <fieldset className="policy-options policy-field-options">
          <legend>允许字段</legend>
          {defaultPolicyFields.map((field) => (
            <label className="check-control" key={field}>
              <input
                type="checkbox"
                checked={draft.allowed_fields.includes(field)}
                disabled={requiredFields.has(field)}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    allowed_fields: event.target.checked
                      ? [...current.allowed_fields, field]
                      : current.allowed_fields.filter((item) => item !== field),
                  }))
                }
              />
              {fieldLabels[field]}
            </label>
          ))}
        </fieldset>
        <label>
          策略版本
          <input
            value={draft.policy_version}
            onChange={(event) => setDraft((current) => ({ ...current, policy_version: event.target.value }))}
            required
          />
        </label>
        <label>
          单次导出上限
          <input
            type="number"
            min={1}
            max={100}
            value={draft.max_records_per_export}
            onChange={(event) =>
              setDraft((current) => ({ ...current, max_records_per_export: Number(event.target.value) }))
            }
            required
          />
        </label>
        <label className="policy-attribution">
          授权标注
          <input
            value={draft.attribution}
            onChange={(event) => setDraft((current) => ({ ...current, attribution: event.target.value }))}
            required
          />
        </label>
        <button className="primary-button" type="submit" disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "保存中" : "保存导出策略"}
        </button>
      </form>
    </section>
  );
}
