import { CheckCircle2, KeyRound, LogOut, Mail, Save } from "lucide-react";
import { type FormEvent, useState } from "react";
import { UserAvatar } from "../components/UserAvatar";
import type { AuthMode } from "../lib/contracts/session";
import { changeCurrentUserPassword, updateCurrentUser } from "../lib/contracts/session";
import { t, uiFeedback, useLocale } from "../lib/i18n";
import type { User } from "../lib/types";

type ProfileDraft = {
  displayName: string;
  email: string;
  phone: string;
  avatarUrl: string;
};

function profileDraftFromUser(user: User): ProfileDraft {
  return {
    displayName: user.display_name,
    email: user.email,
    phone: user.phone ?? "",
    avatarUrl: user.avatar_url ?? "",
  };
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

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
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(() => profileDraftFromUser(user));
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileStatus, setProfileStatus] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [passwordDraft, setPasswordDraft] = useState({ current: "", next: "", confirm: "" });
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordStatus, setPasswordStatus] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileStatus(null);
    const displayName = profileDraft.displayName.trim();
    if (!/[\p{L}\p{N}]/u.test(displayName)) {
      setProfileStatus({ kind: "error", text: "用户名至少需要包含一个文字或数字" });
      return;
    }
    setProfileSaving(true);
    try {
      const updated = await updateCurrentUser({
        display_name: displayName,
        ...(authMode === "oidc" ? {} : { email: profileDraft.email }),
        phone: profileDraft.phone.trim() || null,
        avatar_url: profileDraft.avatarUrl.trim() || null,
      });
      onUserUpdated?.(updated);
      setProfileStatus({ kind: "success", text: "个人资料已更新" });
    } catch (error) {
      setProfileStatus({ kind: "error", text: errorMessage(error, "个人资料保存失败") });
    } finally {
      setProfileSaving(false);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordStatus(null);
    if (passwordDraft.next !== passwordDraft.confirm) {
      setPasswordStatus({ kind: "error", text: "两次输入的新密码不一致" });
      return;
    }
    setPasswordSaving(true);
    try {
      await changeCurrentUserPassword({ current_password: passwordDraft.current, new_password: passwordDraft.next });
      setPasswordDraft({ current: "", next: "", confirm: "" });
      setPasswordStatus({ kind: "success", text: "密码已修改，其他登录会话已退出" });
    } catch (error) {
      setPasswordStatus({ kind: "error", text: errorMessage(error, "密码修改失败") });
    } finally {
      setPasswordSaving(false);
    }
  }

  const draftUser: User = {
    ...user,
    display_name: profileDraft.displayName || user.display_name,
    avatar_url: profileDraft.avatarUrl.trim() || null,
  };

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
        <section className="user-center-panel" aria-labelledby="user-center-profile-title">
          <header className="user-center-panel-header">
            <div>
              <h2 id="user-center-profile-title">{t("个人资料")}</h2>
              <p>{t("更新你的头像和联系方式")}</p>
            </div>
          </header>
          <form className="user-center-form" onSubmit={saveProfile}>
            <div className="user-center-avatar-editor">
              <UserAvatar user={draftUser} className="user-center-avatar" />
              <label className="user-center-field">
                <span>{t("头像图片地址")}</span>
                <input
                  type="url"
                  value={profileDraft.avatarUrl}
                  onChange={(event) => setProfileDraft((current) => ({ ...current, avatarUrl: event.target.value }))}
                  placeholder="https://..."
                  autoComplete="url"
                />
              </label>
            </div>
            <label className="user-center-field">
              <span>{t("用户名")}</span>
              <input
                type="text"
                value={profileDraft.displayName}
                onChange={(event) => {
                  setProfileDraft((current) => ({ ...current, displayName: event.target.value }));
                  setProfileStatus(null);
                }}
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
                value={profileDraft.email}
                onChange={(event) => setProfileDraft((current) => ({ ...current, email: event.target.value }))}
                required
                autoComplete="email"
              />
            </label>
            <label className="user-center-field">
              <span>{t("电话")}</span>
              <input
                type="tel"
                value={profileDraft.phone}
                onChange={(event) => setProfileDraft((current) => ({ ...current, phone: event.target.value }))}
                maxLength={40}
                autoComplete="tel"
              />
            </label>
            {profileStatus ? (
              <p className={`user-center-form-status ${profileStatus.kind}`} role="status">
                {uiFeedback(profileStatus.text)}
              </p>
            ) : null}
            <button className="primary-button" type="submit" disabled={profileSaving}>
              <Save size={16} aria-hidden="true" />
              {profileSaving ? t("保存中…") : t("保存个人资料")}
            </button>
          </form>
        </section>

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
            <form className="user-center-form" onSubmit={savePassword}>
              <label className="user-center-field">
                <span>{t("当前密码")}</span>
                <input
                  type="password"
                  value={passwordDraft.current}
                  onChange={(event) => setPasswordDraft((current) => ({ ...current, current: event.target.value }))}
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
                  value={passwordDraft.next}
                  onChange={(event) => setPasswordDraft((current) => ({ ...current, next: event.target.value }))}
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
                  value={passwordDraft.confirm}
                  onChange={(event) => setPasswordDraft((current) => ({ ...current, confirm: event.target.value }))}
                  minLength={12}
                  maxLength={200}
                  required
                  autoComplete="new-password"
                />
              </label>
              {passwordStatus ? (
                <p className={`user-center-form-status ${passwordStatus.kind}`} role="status">
                  {uiFeedback(passwordStatus.text)}
                </p>
              ) : null}
              <button className="secondary-button" type="submit" disabled={passwordSaving}>
                <KeyRound size={16} aria-hidden="true" />
                {passwordSaving ? t("修改中…") : t("修改密码")}
              </button>
            </form>
          )}
        </section>
      </div>

      <section className="user-center-account-actions" aria-labelledby="user-center-account-actions-title">
        <div>
          <h2 id="user-center-account-actions-title">{t("账户操作")}</h2>
          <p>{t("退出当前账号后，需要重新登录才能继续使用工作台。")}</p>
        </div>
        <button className="secondary-button" type="button" onClick={onLogout}>
          <LogOut size={16} aria-hidden="true" />
          {t("退出当前账号")}
        </button>
      </section>
    </div>
  );
}
