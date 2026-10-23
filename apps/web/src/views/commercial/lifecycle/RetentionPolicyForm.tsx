import { DatabaseBackup } from "lucide-react";
import type { FormEvent } from "react";
import { StatusBadge } from "../../../components/common";
import type { DataRetentionPolicy } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import type { RetentionDraftState } from "./useLifecycleDrafts";

export type RetentionPolicyInput = {
  dataClass: DataRetentionPolicy["data_class"];
  retentionSeconds: number;
  legalBasis: string;
  geographicScope: string[];
  active: boolean;
};
export function RetentionPolicyForm({
  source = false,
  policy,
  draft,
  busy,
  onSave,
}: {
  source?: boolean;
  policy: DataRetentionPolicy | undefined;
  draft: RetentionDraftState;
  busy: boolean;
  onSave: (input: RetentionPolicyInput) => Promise<boolean>;
}) {
  useLocale();
  const seconds = Math.round(Number(draft.hours) * 3600);
  const valid = Number.isSafeInteger(seconds) && seconds >= 300 && draft.basis.trim().length >= 3;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || draft.conflict || !valid) return;
    const submitted = { hours: draft.hours, basis: draft.basis, geography: draft.geography, active: draft.active };
    const succeeded = await onSave({
      dataClass: source ? "source_asset_snapshot" : "commercial_export_artifact",
      retentionSeconds: seconds,
      legalBasis: draft.basis.trim(),
      geographicScope: draft.geography
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
      active: draft.active,
    });
    if (succeeded) draft.acknowledgeSaved(submitted);
  }
  return (
    <form className="operations-form retention-policy-form" onSubmit={submit}>
      <header>
        <h2>{t(source ? "源资料保留策略" : "导出对象保留策略")}</h2>
        <StatusBadge
          value={policy ? (policy.active ? "active" : "inactive") : "not_configured"}
          label={t(policy ? (policy.active ? "已启用" : "未启用") : "尚未配置")}
        />
      </header>
      <label>
        {t(source ? "缺失后保留时长（小时）" : "保留时长（小时）")}
        <input
          aria-label={t(source ? "源资料保留时长（小时）" : "保留时长（小时）")}
          disabled={busy}
          type="number"
          min={5 / 60}
          step="any"
          required
          value={draft.hours}
          onChange={(event) => draft.update({ hours: event.target.value })}
        />
      </label>
      <label>
        {t("法律与合同依据")}
        <input
          aria-label={t(source ? "源资料法律与合同依据" : "法律与合同依据")}
          disabled={busy}
          required
          minLength={3}
          value={draft.basis}
          onChange={(event) => draft.update({ basis: event.target.value })}
          maxLength={500}
        />
      </label>
      <label>
        {t("地域范围")}
        <input
          aria-label={t(source ? "源资料地域范围" : "地域范围")}
          disabled={busy}
          value={draft.geography}
          onChange={(event) => draft.update({ geography: event.target.value })}
          placeholder="CN, SG"
        />
      </label>
      <label className="check-control">
        <input
          type="checkbox"
          disabled={busy}
          checked={draft.active}
          onChange={(event) => draft.update({ active: event.target.checked })}
        />
        {t("启用策略")}
      </label>
      {draft.conflict ? (
        <div className="policy-conflict" role="status">
          <p>{t("策略已在服务端更新。未提交内容已保留，请核对最新策略后再保存。")}</p>
          <button type="button" className="secondary-button" disabled={busy} onClick={draft.useLatest}>
            {t("使用最新策略")}
          </button>
        </div>
      ) : null}
      <button className="primary-button" type="submit" disabled={busy || draft.conflict || !valid}>
        <DatabaseBackup size={16} />
        {t("保存策略")}
      </button>
      {policy ? <p className="form-footnote">{t("当前版本 v{version}", { version: policy.policy_version })}</p> : null}
    </form>
  );
}
