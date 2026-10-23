import { type FormEvent, useEffect, useRef, useState } from "react";
import { pendingIdentityMessage, useIdentityOperation } from "../../components/identity/useIdentityOperation";
import { ApiError } from "../../lib/api";
import { type AuthMode, changeCurrentUserPassword, updateCurrentUser } from "../../lib/contracts/session";
import type { User } from "../../lib/types";

function draftFromUser(user: User) {
  return {
    displayName: user.display_name,
    email: user.email,
    phone: user.phone ?? "",
    avatarUrl: user.avatar_url ?? "",
  };
}
type ProfileDraft = ReturnType<typeof draftFromUser>;
type Feedback = { kind: "success" | "error"; text: string } | null;
const contextChanged = "账号身份已变化，请重新确认后重试。";
function identityKey(user: User) {
  return `${user.id}:${user.tenant_id}:${user.role}`;
}
function failureText(error: unknown, fallback: string, secrets: readonly string[] = []) {
  if (error instanceof Error && error.message === pendingIdentityMessage) return error.message;
  if (error instanceof Error && secrets.some((secret) => secret.length > 0 && error.message.includes(secret)))
    return fallback;
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return error.message;
  return secrets.length === 0 && error instanceof Error && !(error instanceof ApiError) && error.message
    ? error.message
    : fallback;
}

/** UI drafts are local; the existing session contract and server own identity and persistence. */
export function useAccountSettings(user: User, authMode: AuthMode | undefined, onUserUpdated?: (user: User) => void) {
  const operation = useIdentityOperation();
  const identity = useRef(user);
  identity.current = user;
  const mode = useRef(authMode);
  mode.current = authMode;
  const [profileDraft, setProfileDraft] = useState(() => draftFromUser(user));
  const [passwordDraft, setPasswordDraft] = useState({ current: "", next: "", confirm: "" });
  const [profileStatus, setProfileStatus] = useState<Feedback>(null);
  const [passwordStatus, setPasswordStatus] = useState<Feedback>(null);
  useEffect(() => {
    if (authMode === "oidc") {
      setPasswordDraft({ current: "", next: "", confirm: "" });
      setPasswordStatus(null);
    }
  }, [authMode]);
  function editProfile(field: keyof ProfileDraft, value: string) {
    if (operation.isLocked()) return;
    setProfileDraft((draft) => ({ ...draft, [field]: value }));
    setProfileStatus(null);
  }
  function editPassword(field: keyof typeof passwordDraft, value: string) {
    if (operation.isLocked()) return;
    setPasswordDraft((draft) => ({ ...draft, [field]: value }));
    setPasswordStatus(null);
  }
  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (operation.isLocked() || !event.currentTarget.checkValidity()) return;
    setProfileStatus(null);
    const displayName = profileDraft.displayName.trim();
    if (!/[\p{L}\p{N}]/u.test(displayName)) {
      setProfileStatus({ kind: "error", text: "用户名至少需要包含一个文字或数字" });
      return;
    }
    const expected = identityKey(user);
    const payload = {
      display_name: displayName,
      ...(authMode === "oidc" ? {} : { email: profileDraft.email }),
      phone: profileDraft.phone.trim() || null,
      avatar_url: profileDraft.avatarUrl.trim() || null,
    };
    await operation.run(
      "profile",
      async () => {
        const result = await updateCurrentUser(payload);
        if (
          identityKey(identity.current) !== expected ||
          mode.current !== authMode ||
          result.id !== user.id ||
          result.tenant_id !== user.tenant_id
        )
          throw new ApiError(contextChanged, 409, null);
        return result;
      },
      (updated) => {
        setProfileDraft(draftFromUser(updated));
        onUserUpdated?.(updated);
        setProfileStatus({ kind: "success", text: "个人资料已更新" });
      },
      (error) => setProfileStatus({ kind: "error", text: failureText(error, "个人资料保存失败") }),
    );
  }
  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (operation.isLocked() || authMode === "oidc" || !event.currentTarget.checkValidity()) return;
    setPasswordStatus(null);
    if (passwordDraft.next !== passwordDraft.confirm) {
      setPasswordStatus({ kind: "error", text: "两次输入的新密码不一致" });
      return;
    }
    const expected = identityKey(user);
    const payload = { current_password: passwordDraft.current, new_password: passwordDraft.next };
    await operation.run(
      "password",
      async () => {
        await changeCurrentUserPassword(payload);
        if (identityKey(identity.current) !== expected || mode.current !== authMode)
          throw new ApiError(contextChanged, 409, null);
      },
      () => {
        setPasswordDraft({ current: "", next: "", confirm: "" });
        setPasswordStatus({ kind: "success", text: "密码已修改，其他登录会话已退出" });
      },
      (error) =>
        setPasswordStatus({
          kind: "error",
          text: failureText(error, "密码修改失败", [payload.current_password, payload.new_password]),
        }),
    );
  }
  return {
    operation,
    profileDraft,
    profileStatus,
    passwordDraft,
    passwordStatus,
    editProfile,
    editPassword,
    saveProfile,
    savePassword,
  };
}
export type AccountSettings = ReturnType<typeof useAccountSettings>;
