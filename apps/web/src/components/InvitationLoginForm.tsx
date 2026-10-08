import { useMutation } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useState } from "react";
import { ApiError } from "../lib/api";
import { acceptInvitationWithCredentials, startOidcInvitation } from "../lib/contracts/organizations";
import { t, useLocale } from "../lib/i18n";
import type { User } from "../lib/types";

export function InvitationLoginForm({
  mode,
  entryControls,
  onLogin,
}: {
  mode: "local" | "oidc";
  entryControls: ReactNode;
  onLogin: (user: User) => void;
}) {
  useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const acceptance = useMutation({
    mutationFn: async () => {
      if (mode === "oidc") {
        const result = await startOidcInvitation(code.trim());
        window.location.assign(result.authorization_url);
        return;
      }
      return acceptInvitationWithCredentials(email, password, code.trim());
    },
    onSuccess: (user) => {
      setPassword("");
      setCode("");
      if (user) onLogin(user);
    },
    onError: () => {
      setPassword("");
      setCode("");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (confirmed && code.trim()) acceptance.mutate();
  }

  const error =
    acceptance.error instanceof ApiError && acceptance.error.status < 500
      ? acceptance.error.status === 401
        ? t("邮箱或密码不正确，或企业身份验证未通过")
        : acceptance.error.message
      : acceptance.error
        ? t("邀请服务暂不可用，请重新输入邀请码后重试")
        : "";
  return (
    <form className="login-form" onSubmit={submit}>
      {entryControls}
      <h2>{t("已有账号加入组织")}</h2>
      <p className="form-footnote">{t("验证现有账号并接受管理员邀请。原账号、原组织与研究数据保留，不自动共享。")}</p>
      {mode === "local" ? (
        <>
          <label>
            <span>{t("现有账号邮箱")}</span>
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              maxLength={320}
            />
          </label>
          <label>
            <span>{t("现有账号密码")}</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
              maxLength={200}
            />
          </label>
        </>
      ) : (
        <p className="form-footnote">{t("下一步使用已关联的企业身份验证。仅邮箱与邀请一致的已验证身份可以加入。")}</p>
      )}
      <label>
        <span>{t("管理员邀请码")}</span>
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={code}
          onChange={(event) => setCode(event.target.value)}
          required
          maxLength={256}
        />
      </label>
      <label>
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} required />
        <span>{t("我确认加入邀请的组织，不共享原组织数据。")}</span>
      </label>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      <button
        type="submit"
        className="primary-button login-button"
        disabled={
          acceptance.isPending ||
          !confirmed ||
          !code.trim() ||
          (mode === "local" && (!email.trim() || password.length < 8))
        }
      >
        {acceptance.isPending
          ? t("验证邀请中…")
          : mode === "oidc"
            ? t("使用企业身份确认加入")
            : t("验证账号并加入组织")}
      </button>
    </form>
  );
}
