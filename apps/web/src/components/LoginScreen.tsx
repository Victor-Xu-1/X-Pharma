import { useMutation } from "@tanstack/react-query";
import { LockKeyhole, LogIn } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { login } from "../lib/contracts/session";
import { PRODUCT_NAME } from "../lib/product";
import type { User } from "../lib/types";
import type { WorkbenchKey } from "../lib/workspaceRouting";
import { BrandMark } from "./BrandMark";
import { InvitationLoginForm } from "./InvitationLoginForm";
import { RegistrationForm } from "./RegistrationForm";

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "邮箱或密码不正确，请检查后重试";
  if (error instanceof ApiError && error.status === 403) return "没有可用的组织成员资格，请使用管理员邀请码加入组织";
  if (error instanceof ApiError && error.status === 429) return "尝试次数过多，请稍后重试";
  if (error instanceof ApiError && error.status >= 500) return "登录服务暂时不可用，请稍后重试";
  return error ? "登录失败，请稍后重试" : "";
}

export function LoginScreen({
  mode,
  workbench,
  onLogin,
}: {
  mode: "local" | "oidc";
  workbench: WorkbenchKey;
  onLogin: (user: User) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [entry, setEntry] = useState<"login" | "register" | "join">("login");
  const [registeredNotice, setRegisteredNotice] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const authentication = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) => login(email, password),
    onSuccess: (user) => {
      setPassword("");
      onLogin(user);
    },
    onError: () => {
      setPassword("");
      passwordInputRef.current?.focus();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    authentication.mutate({ email, password });
  }

  function clearAuthenticationError() {
    if (authentication.isError) authentication.reset();
  }

  const internal = workbench === "internal";
  const displayError = loginErrorMessage(authentication.error);
  const hasAuthenticationError = Boolean(displayError);
  const credentialsIncomplete = !email.trim() || password.length < 8;
  const entryControls = (
    <nav className="view-tabs" aria-label="账号入口">
      <button
        type="button"
        aria-current={entry === "login" ? "page" : undefined}
        className={entry === "login" ? "active" : ""}
        onClick={() => {
          setEntry("login");
          setPassword("");
          authentication.reset();
        }}
      >
        登录
      </button>
      <button
        type="button"
        aria-current={entry === "register" ? "page" : undefined}
        className={entry === "register" ? "active" : ""}
        onClick={() => {
          setEntry("register");
          setPassword("");
          setRegisteredNotice(false);
          authentication.reset();
        }}
      >
        注册
      </button>
      <button
        type="button"
        aria-current={entry === "join" ? "page" : undefined}
        className={entry === "join" ? "active" : ""}
        onClick={() => {
          setEntry("join");
          setPassword("");
          authentication.reset();
        }}
      >
        加入组织
      </button>
    </nav>
  );

  return (
    <main className="login-screen">
      <section className="login-brand" aria-label={internal ? "内部管理平台" : PRODUCT_NAME}>
        <div className="brand-lockup brand-lockup-large">
          <BrandMark />
          <span>
            <strong>{PRODUCT_NAME}</strong>
            <small>{internal ? "数据治理与运营管理" : "生物医药研发情报平台"}</small>
          </span>
        </div>
        <div className="login-title">
          <p className="eyebrow">{internal ? "内部管理" : "研发情报平台"}</p>
          <h1>{internal ? "内部管理工作台" : "医药情报工作台"}</h1>
          <p>{internal ? "数据接入、AI 治理、商业运营与企业审计" : "药物、靶点、临床、专利与交易数据"}</p>
        </div>
        <p className="login-version">{internal ? "仅限授权内部人员" : "专业数据检索与关联分析"}</p>
      </section>
      <section className="login-form-area">
        {entry === "register" ? (
          <RegistrationForm
            workbench={workbench}
            entryControls={entryControls}
            onRegistered={(registeredEmail) => {
              setEmail(registeredEmail);
              setEntry("login");
              setRegisteredNotice(true);
            }}
          />
        ) : entry === "join" ? (
          <InvitationLoginForm mode={mode} entryControls={entryControls} onLogin={onLogin} />
        ) : (
          <form className="login-form" onSubmit={submit}>
            {entryControls}
            <LockKeyhole size={24} aria-hidden="true" />
            <div>
              <p className="eyebrow">{internal ? "管理员登录" : "账号登录"}</p>
              <h2>{mode === "oidc" ? "企业身份登录" : "账户登录"}</h2>
            </div>
            {registeredNotice ? (
              <p className="form-footnote" role="status">
                注册成功，请使用刚设置的密码登录。
              </p>
            ) : null}
            {mode === "oidc" ? (
              <a className="primary-button login-button" href="/api/v1/auth/oidc/login">
                <LogIn size={17} />
                使用企业身份登录
              </a>
            ) : (
              <>
                <label>
                  <span>工作邮箱</span>
                  <input
                    type="email"
                    autoComplete="username"
                    value={email}
                    aria-invalid={hasAuthenticationError || undefined}
                    aria-describedby={hasAuthenticationError ? "login-error" : undefined}
                    onChange={(event) => {
                      clearAuthenticationError();
                      setEmail(event.target.value);
                    }}
                    required
                  />
                </label>
                <label>
                  <span>密码</span>
                  <input
                    ref={passwordInputRef}
                    type="password"
                    autoComplete="current-password"
                    minLength={8}
                    value={password}
                    aria-invalid={hasAuthenticationError || undefined}
                    aria-describedby={hasAuthenticationError ? "login-error" : undefined}
                    onChange={(event) => {
                      clearAuthenticationError();
                      setPassword(event.target.value);
                    }}
                    required
                  />
                </label>
                {displayError ? (
                  <p id="login-error" className="form-error" role="alert">
                    {displayError}
                  </p>
                ) : null}
                <button
                  className="primary-button login-button"
                  type="submit"
                  disabled={authentication.isPending || credentialsIncomplete}
                >
                  {authentication.isPending ? "验证中" : "进入工作台"}
                </button>
              </>
            )}
          </form>
        )}
      </section>
    </main>
  );
}
