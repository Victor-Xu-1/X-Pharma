import { CheckCircle2, LogOut, Mail } from "lucide-react";
import { UserAvatar } from "../components/UserAvatar";
import type { AuthMode } from "../lib/contracts/session";
import { t, useLocale } from "../lib/i18n";
import type { User } from "../lib/types";
import { PasswordForm } from "./account/PasswordForm";
import { ProfileForm } from "./account/ProfileForm";
import { useAccountSettings } from "./account/useAccountSettings";

export function OverviewView({
  user,
  authMode,
  onLogout,
  onUserUpdated,
}: {
  user: User;
  authMode?: AuthMode;
  onLogout: () => void;
  onUserUpdated?: (user: User) => void;
}) {
  useLocale();
  const settings = useAccountSettings(user, authMode, onUserUpdated);
  return (
    <div className="user-center-layout">
      <section className="user-center-identity-card" aria-labelledby="user-center-identity-title">
        <UserAvatar user={user} className="user-center-identity-avatar" />
        <div className="user-center-identity-copy">
          <p className="user-center-eyebrow">{t("账户信息")}</p>
          <h2 id="user-center-identity-title">{user.display_name}</h2>
          <span>
            <Mail size={15} aria-hidden="true" />
            {user.email}
          </span>
        </div>
        <span className="user-center-status">
          <CheckCircle2 size={16} aria-hidden="true" />
          {t("账户正常")}
        </span>
      </section>
      {authMode === "local" ? (
        <p className="field-help">
          {t(
            "本地账号：邮箱仅作为登录标识，尚未验证邮箱归属；忘记密码请联系本地管理员。正式部署需要企业身份与恢复策略。",
          )}
        </p>
      ) : authMode === "oidc" ? (
        <p className="field-help">{t("企业账号：登录、邮箱身份、密码及恢复由企业身份服务管理。")}</p>
      ) : null}
      <div className="user-center-settings-grid">
        <ProfileForm user={user} authMode={authMode} settings={settings} />
        <PasswordForm authMode={authMode} settings={settings} />
      </div>
      <section className="user-center-account-actions" aria-labelledby="user-center-account-actions-title">
        <div>
          <h2 id="user-center-account-actions-title">{t("账户操作")}</h2>
          <p>{t("退出当前账号后，需要重新登录才能继续使用工作台。")}</p>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={Boolean(settings.operation.pending)}
          onClick={() => {
            if (!settings.operation.isLocked()) onLogout();
          }}
        >
          <LogOut size={16} aria-hidden="true" />
          {t("退出当前账号")}
        </button>
      </section>
    </div>
  );
}
