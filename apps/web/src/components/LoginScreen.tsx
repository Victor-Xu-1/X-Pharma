import { useMutation } from "@tanstack/react-query";
import { Database, LockKeyhole, LogIn } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { login } from "../lib/contracts/session";
import { PRODUCT_NAME } from "../lib/product";
import type { User } from "../lib/types";
import type { WorkbenchKey } from "../lib/workspaceRouting";

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "邮箱或密码不正确，请检查后重试";
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

  return (
    <main className="login-screen">
      <section className="login-brand" aria-label={internal ? "内部管理平台" : PRODUCT_NAME}>
        <div className="brand-lockup brand-lockup-large">
          <span className="brand-symbol">
            <Database size={22} />
          </span>
          <span>
            <strong>{internal ? "内部管理平台" : PRODUCT_NAME}</strong>
            <small>{internal ? "数据治理与运营管理" : "生物医药研发情报平台"}</small>
          </span>
        </div>
        <div className="login-title">
          <p className="eyebrow">{internal ? "内部管理" : "研发情报平台"}</p>
          <h1>{internal ? "内部管理工作台" : "医药情报工作台"}</h1>
          <p>{internal ? "数据接入、AI 治理、商业运营与企业审计" : "药物、靶点、临床、专利与交易数据"}</p>
        </div>
        <p className="login-version">{internal ? "仅限授权管理员" : "专业数据检索与关联分析"}</p>
      </section>
      <section className="login-form-area">
        <form className="login-form" onSubmit={submit}>
          <LockKeyhole size={24} aria-hidden="true" />
          <div>
            <p className="eyebrow">{internal ? "管理员登录" : "账号登录"}</p>
            <h2>{mode === "oidc" ? "企业身份登录" : "账户登录"}</h2>
          </div>
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
      </section>
    </main>
  );
}
