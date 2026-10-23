import { Save } from "lucide-react";
import { FormStatus } from "../../components/FormStatus";
import { UserAvatar } from "../../components/UserAvatar";
import type { AuthMode } from "../../lib/contracts/session";
import { t, uiFeedback } from "../../lib/i18n";
import type { User } from "../../lib/types";
import type { AccountSettings } from "./useAccountSettings";

export function ProfileForm({
  user,
  authMode,
  settings,
}: {
  user: User;
  authMode?: AuthMode;
  settings: AccountSettings;
}) {
  const { operation, profileDraft: draft, editProfile, profileStatus: status } = settings;
  const draftUser = {
    ...user,
    display_name: draft.displayName || user.display_name,
    avatar_url: draft.avatarUrl.trim() || null,
  };
  return (
    <section className="user-center-panel" aria-labelledby="user-center-profile-title">
      <header className="user-center-panel-header">
        <div>
          <h2 id="user-center-profile-title">{t("个人资料")}</h2>
          <p>{t("更新你的头像和联系方式")}</p>
        </div>
      </header>
      <form className="user-center-form" onSubmit={settings.saveProfile} aria-busy={operation.pending === "profile"}>
        <fieldset className="user-center-form-fields" aria-label={t("个人资料")} disabled={Boolean(operation.pending)}>
          <div className="user-center-avatar-editor">
            <UserAvatar user={draftUser} className="user-center-avatar" />
            <label className="user-center-field">
              <span>{t("头像图片地址")}</span>
              <input
                type="url"
                value={draft.avatarUrl}
                onChange={(event) => editProfile("avatarUrl", event.target.value)}
                placeholder="https://..."
                autoComplete="url"
              />
            </label>
          </div>
          <label className="user-center-field">
            <span>{t("用户名")}</span>
            <input
              type="text"
              value={draft.displayName}
              onChange={(event) => editProfile("displayName", event.target.value)}
              minLength={1}
              maxLength={200}
              required
              autoComplete="name"
            />
          </label>
          <label className="user-center-field">
            <span>{t("邮箱")}</span>
            <input
              type="email"
              readOnly={authMode === "oidc"}
              value={draft.email}
              onChange={(event) => editProfile("email", event.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label className="user-center-field">
            <span>{t("电话")}</span>
            <input
              type="tel"
              value={draft.phone}
              onChange={(event) => editProfile("phone", event.target.value)}
              maxLength={40}
              autoComplete="tel"
            />
          </label>
        </fieldset>
        <FormStatus
          pending={operation.pending === "profile"}
          pendingLabel={t("保存中…")}
          error={status?.kind === "error" ? uiFeedback(status.text) : undefined}
        />
        {status?.kind === "success" ? (
          <p className="user-center-form-status" role="status">
            {uiFeedback(status.text)}
          </p>
        ) : null}
        <button className="primary-button" type="submit" disabled={Boolean(operation.pending)}>
          <Save size={16} aria-hidden="true" />
          {t("保存个人资料")}
        </button>
      </form>
    </section>
  );
}
