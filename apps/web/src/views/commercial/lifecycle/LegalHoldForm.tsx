import { Gavel } from "lucide-react";
import type { FormEvent } from "react";
import type { LegalHoldScope } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import type { LifecycleDraftState } from "./useLifecycleDrafts";

export type LegalHoldInput = {
  scopeType: LegalHoldScope;
  scopeId: string | null;
  matterReference: string;
  reason: string;
};
export function LegalHoldForm({
  drafts,
  busy,
  onPlace,
}: {
  drafts: LifecycleDraftState;
  busy: boolean;
  onPlace: (input: LegalHoldInput) => Promise<boolean>;
}) {
  useLocale();
  const draft = drafts.hold;
  const valid =
    draft.matterReference.trim().length >= 3 &&
    draft.reason.trim().length >= 3 &&
    (draft.scopeType === "tenant" || Boolean(draft.scopeId.trim()));
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !valid) return;
    const succeeded = await onPlace({
      scopeType: draft.scopeType,
      scopeId: draft.scopeType === "tenant" ? null : draft.scopeId.trim(),
      matterReference: draft.matterReference.trim(),
      reason: draft.reason.trim(),
    });
    if (succeeded) drafts.acknowledgeHold();
  }
  return (
    <form className="operations-form" onSubmit={submit}>
      <header>
        <h2>{t("创建法律保全")}</h2>
        <Gavel size={18} />
      </header>
      <label>
        {t("保全范围")}
        <select
          aria-label={t("保全范围")}
          disabled={busy}
          value={draft.scopeType}
          onChange={(event) => drafts.updateHold({ scopeType: event.target.value as LegalHoldScope })}
        >
          <option value="tenant">{t("整个租户")}</option>
          <option value="billing_account">{t("计费账户")}</option>
          <option value="data_export_job">{t("导出任务")}</option>
          <option value="data_source">{t("资料源")}</option>
          <option value="source_asset">{t("源资料资产")}</option>
        </select>
      </label>
      {draft.scopeType !== "tenant" ? (
        <label>
          {t("范围 ID")}
          <input
            aria-label={t("保全范围 ID")}
            disabled={busy}
            value={draft.scopeId}
            onChange={(event) => drafts.updateHold({ scopeId: event.target.value })}
            required
          />
        </label>
      ) : null}
      <label>
        {t("事项编号")}
        <input
          aria-label={t("事项编号")}
          disabled={busy}
          value={draft.matterReference}
          onChange={(event) => drafts.updateHold({ matterReference: event.target.value })}
          required
          minLength={3}
          maxLength={200}
        />
      </label>
      <label>
        {t("保全原因")}
        <textarea
          aria-label={t("保全原因")}
          disabled={busy}
          value={draft.reason}
          onChange={(event) => drafts.updateHold({ reason: event.target.value })}
          required
          minLength={3}
          maxLength={2000}
        />
      </label>
      <button className="primary-button" type="submit" disabled={busy || !valid}>
        <Gavel size={16} />
        {t("启动保全")}
      </button>
    </form>
  );
}
