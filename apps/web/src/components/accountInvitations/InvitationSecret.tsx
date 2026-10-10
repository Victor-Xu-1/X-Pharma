import { Copy, X } from "lucide-react";
import { useState } from "react";
import type { InvitationIssued } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { type AccountInvitationMessageKey, accountInvitationText as t } from "../../lib/i18n/accountInvitations";
import { useModalFocus } from "../../lib/useModalFocus";
import { formatDate } from "../common";

export function InvitationSecret({ issued, close }: { issued: InvitationIssued; close: () => void }) {
  useLocale();
  const ref = useModalFocus<HTMLElement>(true, close);
  const [copyStatus, setCopyStatus] = useState<AccountInvitationMessageKey | null>(null);
  async function copy() {
    try {
      await navigator.clipboard.writeText(issued.code);
      setCopyStatus("邀请码已复制");
    } catch {
      setCopyStatus("无法写入剪贴板，请选中邀请码手动复制");
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={t("新生成的注册邀请码")}
        tabIndex={-1}
        ref={ref}
      >
        <header>
          <h3>{t("注册邀请码")}</h3>
          <button className="icon-button" type="button" onClick={close} aria-label={t("关闭邀请码")}>
            <X size={18} />
          </button>
        </header>
        <div className="account-invitation-content">
          <p>
            {t("绑定邮箱：")}
            {issued.invitation.email}
          </p>
          <p>
            {t("有效期至：")}
            {formatDate(issued.invitation.expires_at, true)}
          </p>
          <label>
            <span>{t("一次性邀请码")}</span>
            <input
              value={issued.code}
              readOnly
              onFocus={(event) => event.currentTarget.select()}
              data-modal-autofocus="true"
            />
          </label>
          <p className="form-footnote">{t("邀请码仅显示这一次。请私下交给绑定邮箱的用户；注册后立即失效。")}</p>
          <button className="secondary-button" type="button" onClick={() => void copy()}>
            <Copy size={16} />
            {t("复制邀请码")}
          </button>
          {copyStatus ? <p role="status">{t(copyStatus)}</p> : null}
          <button className="primary-button" type="button" onClick={close}>
            {t("完成")}
          </button>
        </div>
      </section>
    </div>
  );
}
