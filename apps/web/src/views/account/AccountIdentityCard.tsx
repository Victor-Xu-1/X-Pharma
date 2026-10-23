import { Mail } from "lucide-react";
import { UserAvatar } from "../../components/UserAvatar";
import type { AuthMode } from "../../lib/contracts/session";
import { t } from "../../lib/i18n";
import type { User } from "../../lib/types";

/** Presents only known identity and authentication-mode facts; no inferred account health. */
export function AccountIdentityCard({ user, authMode }: { user: User; authMode?: AuthMode }) {
  const guidance =
    authMode === "local"
      ? t("本地账号：邮箱仅作为登录标识，尚未验证邮箱归属；忘记密码请联系本地管理员。正式部署需要企业身份与恢复策略。")
      : authMode === "oidc"
        ? t("企业账号：登录、邮箱身份、密码及恢复由企业身份服务管理。")
        : null;
  return (
    <section className="user-center-identity-card" aria-labelledby="user-center-identity-title">
      <UserAvatar user={user} className="user-center-identity-avatar" />
      <div className="user-center-identity-copy">
        <h2 id="user-center-identity-title">{user.display_name}</h2>
        <span>
          <Mail size={15} aria-hidden="true" />
          {user.email}
        </span>
      </div>
      {guidance ? (
        <div className="user-center-sign-in-note">
          <p>{authMode === "local" ? t("邮箱归属未验证。") : t("登录与恢复由企业身份服务管理。")}</p>
          <details>
            <summary>{t("登录与恢复说明")}</summary>
            <p>{guidance}</p>
          </details>
        </div>
      ) : null}
    </section>
  );
}
