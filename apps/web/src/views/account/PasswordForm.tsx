import { KeyRound } from "lucide-react";
import { FormStatus } from "../../components/FormStatus";
import type { AuthMode } from "../../lib/contracts/session";
import { t, uiFeedback } from "../../lib/i18n";
import type { AccountSettings } from "./useAccountSettings";

export function PasswordForm({ authMode, settings }: { authMode?: AuthMode; settings: AccountSettings }) {
  const { operation, passwordDraft: draft, editPassword, passwordStatus: status } = settings;
  return (
    <section className="user-center-panel" aria-labelledby="user-center-security-title">
      <header className="user-center-panel-header">
        <div>
          <h2 id="user-center-security-title">{t("登录安全")}</h2>
          <p>{authMode === "oidc" ? t("密码与账号恢复请前往企业身份服务") : t("修改密码后，其他登录会话会退出")}</p>
        </div>
        <KeyRound size={20} aria-hidden="true" />
      </header>
      {authMode === "oidc" ? (
        <p>{t("本软件不会接收或修改企业密码，也不会提供本地密码登录回退。")}</p>
      ) : (
        <form
          className="user-center-form"
          onSubmit={settings.savePassword}
          aria-busy={operation.pending === "password"}
        >
          <fieldset
            className="user-center-form-fields"
            aria-label={t("登录安全")}
            disabled={Boolean(operation.pending)}
          >
            <label className="user-center-field">
              <span>{t("当前密码")}</span>
              <input
                type="password"
                value={draft.current}
                onChange={(event) => editPassword("current", event.target.value)}
                minLength={8}
                maxLength={200}
                required
                autoComplete="current-password"
              />
            </label>
            <label className="user-center-field">
              <span>{t("新密码")}</span>
              <input
                type="password"
                value={draft.next}
                onChange={(event) => editPassword("next", event.target.value)}
                minLength={12}
                maxLength={200}
                required
                autoComplete="new-password"
              />
            </label>
            <label className="user-center-field">
              <span>{t("确认新密码")}</span>
              <input
                type="password"
                value={draft.confirm}
                onChange={(event) => editPassword("confirm", event.target.value)}
                minLength={12}
                maxLength={200}
                required
                autoComplete="new-password"
              />
            </label>
          </fieldset>
          <FormStatus
            pending={operation.pending === "password"}
            pendingLabel={t("修改中…")}
            error={status?.kind === "error" ? uiFeedback(status.text) : undefined}
          />
          {status?.kind === "success" ? (
            <p className="user-center-form-status" role="status">
              {uiFeedback(status.text)}
            </p>
          ) : null}
          <button className="secondary-button" type="submit" disabled={Boolean(operation.pending)}>
            <KeyRound size={16} aria-hidden="true" />
            {t("修改密码")}
          </button>
        </form>
      )}
    </section>
  );
}
