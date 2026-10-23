import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { BillingDisputeAction } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { useModalFocus } from "../../lib/useModalFocus";
import type { DisputeCaseAction } from "./types";

export function BillingDisputeTransitionModal({
  action,
  notes,
  assignee,
  units,
  adjustmentKey,
  busy,
  error = "",
  onAction,
  onNotes,
  onAssignee,
  onUnits,
  onAdjustmentKey,
  onClose,
  onSubmit,
}: {
  action: DisputeCaseAction;
  notes: string;
  assignee: string;
  units: string;
  adjustmentKey: string;
  busy: boolean;
  error?: string;
  onAction: (value: BillingDisputeAction) => void;
  onNotes: (value: string) => void;
  onAssignee: (value: string) => void;
  onUnits: (value: string) => void;
  onAdjustmentKey: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  useLocale();
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  const credit = action.action === "resolve_credit";
  const valid = notes.trim().length >= 3 && (!credit || (Number(units) > 0 && adjustmentKey.trim().length >= 8));
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="transition-dispute-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">BILLING DISPUTE</p>
            <h2 id="transition-dispute-title">{t("处理计费争议")}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.dispute.subject}
            <span>{action.dispute.description}</span>
            <span className="mono-cell">
              {t("争议额度 {units} · 版本 {version}", {
                units: action.dispute.disputed_units,
                version: action.dispute.version,
              })}
            </span>
          </p>
          <label>
            <span>{t("处理动作")}</span>
            <select
              aria-label={t("争议处理动作")}
              disabled={busy}
              value={action.action}
              onChange={(event) => onAction(event.target.value as BillingDisputeAction)}
            >
              {action.dispute.status === "open" ? <option value="investigate">{t("受理并调查")}</option> : null}
              {action.dispute.status === "investigating" ? (
                <option value="resolve_no_credit">{t("确认无退款")}</option>
              ) : null}
              {action.dispute.status === "investigating" ? (
                <option value="resolve_credit">{t("退款额度")}</option>
              ) : null}
              {action.dispute.status === "investigating" ? <option value="reject">{t("驳回")}</option> : null}
              <option value="cancel">{t("取消案件")}</option>
            </select>
          </label>
          <label>
            <span>{t("负责人")}</span>
            <input
              disabled={busy}
              maxLength={500}
              value={assignee}
              onChange={(event) => onAssignee(event.target.value)}
            />
          </label>
          {credit ? (
            <>
              <label>
                <span>{t("退款额度")}</span>
                <input
                  aria-label={t("退款额度")}
                  disabled={busy}
                  type="number"
                  min="0.00000001"
                  max={action.dispute.disputed_units}
                  step="0.00000001"
                  required
                  value={units}
                  onChange={(event) => onUnits(event.target.value)}
                />
              </label>
              <label>
                <span>{t("账本调整键")}</span>
                <input
                  aria-label={t("账本调整键")}
                  disabled={busy}
                  minLength={8}
                  maxLength={199}
                  required
                  value={adjustmentKey}
                  onChange={(event) => onAdjustmentKey(event.target.value)}
                />
              </label>
            </>
          ) : null}
          <label>
            <span>{t("处理记录")}</span>
            <textarea
              aria-label={t("争议处理记录")}
              disabled={busy}
              rows={4}
              minLength={3}
              maxLength={4000}
              required
              value={notes}
              onChange={(event) => onNotes(event.target.value)}
            />
          </label>
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              {t("取消")}
            </button>
            <button className="primary-button" type="submit" disabled={busy || !valid}>
              {t("提交处理")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
