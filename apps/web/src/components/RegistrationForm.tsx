import { useMutation, useQuery } from "@tanstack/react-query";
import { UserRoundPlus } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";

import { ApiError } from "../lib/api";
import { registerAccount, registrationPolicy } from "../lib/contracts/accounts";
import type { WorkbenchKey } from "../lib/workspaceRouting";
import { ErrorState, Spinner } from "./common";

function registrationError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "注册尝试过多，请稍后重试";
    if (error.status === 413) return "注册内容过长，请减少输入后重试";
    if (error.status >= 500) return "注册服务暂不可用，请稍后重试";
    if ([403, 409].includes(error.status)) return error.message;
    if (error.status === 422) return "请检查邮箱、用户名、密码和邀请码";
  }
  return "注册失败，请检查网络后重试";
}

export function RegistrationForm({
  workbench,
  entryControls,
  onRegistered,
}: {
  workbench: WorkbenchKey;
  entryControls: ReactNode;
  onRegistered: (email: string) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [code, setCode] = useState("");
  const [validation, setValidation] = useState("");
  const policy = useQuery({
    queryKey: ["account", "registration-policy"],
    queryFn: ({ signal }) => registrationPolicy(signal),
  });
  const registration = useMutation({
    mutationFn: registerAccount,
    onSuccess: (user) => {
      setPassword("");
      setConfirmation("");
      setCode("");
      onRegistered(user.email);
    },
    onError: () => {
      setPassword("");
      setConfirmation("");
    },
  });
  const internal = workbench === "internal";
  const minimum = Math.max(12, policy.data?.password_min_length ?? 12);
  const enabled = policy.data?.[workbench] !== "disabled";
  const error = validation || (registration.error ? registrationError(registration.error) : "");
  const incomplete =
    !name.trim() || !email.trim() || password.length < minimum || !confirmation || (internal && !code.trim());

  function submit(event: FormEvent) {
    event.preventDefault();
    setValidation("");
    if (!/[\p{L}\p{N}]/u.test(name)) {
      setValidation("用户名至少包含一个文字或数字");
      return;
    }
    if (password !== confirmation) {
      setValidation("两次输入的密码不一致");
      return;
    }
    registration.mutate({
      workbench,
      display_name: name.trim(),
      email: email.trim(),
      password,
      ...(internal ? { invitation_code: code.trim() } : {}),
    });
  }

  return (
    <form className="login-form" onSubmit={submit}>
      {entryControls}
      <UserRoundPlus size={24} aria-hidden="true" />
      <h2>{internal ? "邀请码注册" : "注册独立账号"}</h2>
      {policy.isPending ? (
        <Spinner label="正在读取注册设置" />
      ) : policy.error ? (
        <ErrorState message="注册设置读取失败" retry={() => void policy.refetch()} />
      ) : !enabled ? (
        <p role="status">当前账号由组织身份系统或管理员管理，请使用登录入口或联系管理员开通。</p>
      ) : (
        <>
          <p className="form-footnote">
            {internal
              ? "邀请码由管理员发放，绑定邮箱并且只能使用一次。新账号默认是内部分析员。"
              : "独立账号不自动获得内部管理权限或其他企业的数据授权。"}
          </p>
          <label>
            <span>用户名</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={200}
              autoComplete="name"
            />
          </label>
          <label>
            <span>注册邮箱</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              maxLength={320}
              autoComplete="username"
            />
          </label>
          {internal ? (
            <label>
              <span>管理员邀请码</span>
              <input
                type="password"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                required
                maxLength={256}
                autoComplete="off"
                spellCheck={false}
              />
            </label>
          ) : null}
          <label>
            <span>设置密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={minimum}
              maxLength={256}
              autoComplete="new-password"
            />
          </label>
          <label>
            <span>确认密码</span>
            <input
              type="password"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              required
              minLength={minimum}
              maxLength={256}
              autoComplete="new-password"
            />
          </label>
          <p className="form-footnote">密码至少 {minimum} 个字符。邮箱作为本地登录标识，不作为已验证的企业身份。</p>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="primary-button login-button" type="submit" disabled={registration.isPending || incomplete}>
            {registration.isPending ? "注册中…" : "创建账号"}
          </button>
        </>
      )}
    </form>
  );
}
