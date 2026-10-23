import type { FormEvent } from "react";
import { ErrorState, Spinner } from "../components/common";
import { useLocale } from "../lib/i18n";
import { workspacePolicyText as t } from "../lib/i18n/workspacePolicy";
import { useWorkspacePolicy, type WorkspacePolicyDrafts } from "./commercial/policy/useWorkspacePolicy";
import { WorkspacePolicyFields } from "./commercial/policy/WorkspacePolicyFields";
import type { CommercialOperationBoundary } from "./commercial/useCommercialOperationBoundary";

export function WorkspaceExportPolicyPanel({
  boundary,
  draftState,
}: {
  boundary: CommercialOperationBoundary;
  draftState: WorkspacePolicyDrafts;
}) {
  useLocale();
  const model = useWorkspacePolicy(boundary, draftState);
  const { draft, query, busy } = model;
  if (query.isPending) return <Spinner label={t("正在加载工作台导出策略")} />;
  if (query.error)
    return (
      <ErrorState
        message={query.error instanceof Error ? query.error.message : t("工作台导出策略加载失败")}
        retry={() => void query.refetch()}
      />
    );
  function submit(event: FormEvent) {
    event.preventDefault();
    void model.save();
  }
  return (
    <section className="export-policy-admin" aria-labelledby="workspace-export-policy-title">
      <div className="section-toolbar">
        <div>
          <h2 id="workspace-export-policy-title">{t("工作台导出策略")}</h2>
          <p className="field-help">{t("控制外部用户工作台可导出的格式字段单次上限和授权标注")}</p>
        </div>
      </div>
      {model.error || model.mismatch ? (
        <p className="inline-error" role="alert">
          {model.error || t("保存返回的策略与原版本不匹配；请重新读取后核对。")}
        </p>
      ) : null}
      {model.savedVersion ? (
        <p className="inline-feedback" role="status">
          {t("导出策略 {version} 已生效", { version: model.savedVersion })}
        </p>
      ) : null}
      {model.conflict ? (
        <div className="policy-conflict" role="status">
          <p>{t("策略已在服务端更新。未提交内容已保留，请核对最新策略后再保存。")}</p>
          <button className="text-button" type="button" disabled={busy || query.isFetching} onClick={model.useLatest}>
            {t("使用最新策略")}
          </button>
        </div>
      ) : null}
      <form className="policy-form" onSubmit={submit}>
        <fieldset className="policy-edit-boundary" disabled={busy}>
          <header>
            <div>
              <strong>
                {query.data ? t("当前版本 {version}", { version: query.data.policy_version }) : t("尚未配置导出策略")}
              </strong>
              <small>{t("策略变更必须使用新版本号历史导出事件保持不可修改")}</small>
            </div>
            <label className="check-control">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) => model.update({ ...draft, enabled: event.target.checked })}
              />
              {t("启用外部工作台人工导出")}
            </label>
          </header>
          <div className="policy-config-row">
            <label>
              {t("策略版本")}
              <input
                required
                value={draft.policy_version}
                onChange={(event) => model.update({ ...draft, policy_version: event.target.value })}
              />
            </label>
            <label>
              {t("单次导出上限")}
              <input
                required
                type="number"
                min={1}
                max={100}
                value={draft.max_records_per_export}
                onChange={(event) => model.update({ ...draft, max_records_per_export: Number(event.target.value) })}
              />
            </label>
            <label className="policy-attribution">
              {t("授权标注")}
              <input
                required
                value={draft.attribution}
                onChange={(event) => model.update({ ...draft, attribution: event.target.value })}
              />
            </label>
          </div>
          <fieldset className="policy-options">
            <legend>{t("允许格式")}</legend>
            {(["csv", "json", "xlsx"] as const).map((format) => (
              <label className="check-control" key={format}>
                <input
                  type="checkbox"
                  checked={draft.allowed_formats.includes(format)}
                  disabled={draft.allowed_formats.length === 1 && draft.allowed_formats.includes(format)}
                  onChange={(event) =>
                    model.update({
                      ...draft,
                      allowed_formats: event.target.checked
                        ? [...draft.allowed_formats, format]
                        : draft.allowed_formats.filter((item) => item !== format),
                    })
                  }
                />
                {format.toUpperCase()}
              </label>
            ))}
          </fieldset>
          <WorkspacePolicyFields
            draft={draft}
            onChange={model.update}
            expandedGroups={draftState.expandedGroups}
            onExpandedChange={draftState.setExpandedGroups}
          />
        </fieldset>
        <button className="primary-button" type="submit" disabled={busy || query.isFetching || model.conflict}>
          {busy ? t("保存中") : t("保存导出策略")}
        </button>
      </form>
    </section>
  );
}
