import { X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { FormStatus } from "../../../components/FormStatus";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import { useModalFocus } from "../../../lib/useModalFocus";
import type { LifecycleAction, LifecycleConfirmation } from "./types";

export function LifecycleActionModal({
  action,
  busy,
  error,
  current,
  onClose,
  onConfirm,
}: {
  action: LifecycleAction;
  busy: boolean;
  error: string;
  current: boolean;
  onClose: () => void;
  onConfirm: (intent: LifecycleConfirmation) => Promise<boolean>;
}) {
  useLocale();
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [captured, setCaptured] = useState<LifecycleConfirmation | null>(null);
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  const title =
    action.kind === "release"
      ? "解除法律保全"
      : action.kind === "source-purge"
        ? "撤回源资料"
        : action.kind === "source-reauthorize"
          ? "重新授权源资料"
          : "清除到期导出对象";
  const target = action.kind === "release" ? action.hold : action.kind === "purge" ? action.job : action.asset;
  const source = action.kind === "source-purge" || action.kind === "source-reauthorize" ? action.asset : null;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !current || !acknowledged || reason.trim().length < 3) return;
    const prefix =
      action.kind === "purge"
        ? "web.purge."
        : action.kind === "source-purge"
          ? "web.source-purge."
          : "web.source-reauthorize.";
    const intent: LifecycleConfirmation =
      captured ??
      (action.kind === "release"
        ? { kind: "release", reason: reason.trim() }
        : { kind: action.kind, reason: reason.trim(), key: prefix + crypto.randomUUID() });
    setCaptured(intent);
    if (await onConfirm(intent)) onClose();
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="lifecycle-action-title"
        tabIndex={-1}
      >
        <header>
          <h2 id="lifecycle-action-title">{t(title)}</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <div className="lifecycle-action-target">
          <p>{t("目标")}</p>
          <strong>
            {action.kind === "release"
              ? action.hold.matter_reference
              : action.kind === "purge"
                ? action.job.dataset
                : action.asset.file_name}
          </strong>
          <code>{target.id}</code>
          {source ? <code>{source.logical_path}</code> : null}
          {action.kind === "purge" || action.kind === "source-purge" ? (
            <p>{t("这将请求清除该目标的对象；服务端仍将核对保留策略、法律保全与业务依赖。")}</p>
          ) : null}
          {!current ? <p role="status">{t("此目标已更新。请关闭此对话框并核对最新记录。")}</p> : null}
        </div>
        <form onSubmit={submit}>
          <label>
            {t("操作原因")}
            <textarea
              aria-label={t("生命周期操作原因")}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
              minLength={3}
              maxLength={2000}
              disabled={busy || Boolean(captured)}
            />
          </label>
          <label className="check-control">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
              disabled={busy || Boolean(captured)}
            />
            {t("我已核对目标并了解此操作")}
          </label>
          {captured ? (
            <p className="form-footnote">
              {t(
                captured.kind === "release"
                  ? "重试将复用同一目标和原因。解除保全接口没有操作键；重试前请核对最新保全记录。"
                  : "重试将复用同一目标、原因和操作键。若需修改，请取消并重新开始。",
              )}
            </p>
          ) : null}
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              {t("取消")}
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={busy || !current || !acknowledged || reason.trim().length < 3}
            >
              {t("确认执行")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
