import { LogOut } from "lucide-react";
import type { AuthMode } from "../lib/contracts/session";
import { t, useLocale } from "../lib/i18n";
import type { User } from "../lib/types";
import { AccountIdentityCard } from "./account/AccountIdentityCard";
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
      <AccountIdentityCard user={user} authMode={authMode} />
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
