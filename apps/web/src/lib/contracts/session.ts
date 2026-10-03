import { ApiError } from "../api";
import { contractRequest } from "../contract";
import type { EntityRead, UserPasswordChange, UserProfileUpdate, UserRead } from "../generated";
import { AuthenticationService, EntitiesService } from "../generated";
import type { User } from "../types";

export type AuthMode = "local" | "oidc";
export type SessionSnapshot = { mode: AuthMode; user: User | null };

export const sessionKeys = {
  current: ["session", "current"] as const,
  entity: (entityId: string) => ["session", "entity", entityId] as const,
};

const sessionRequestTimeoutMs = 10_000;

export async function loadSession(signal?: AbortSignal): Promise<SessionSnapshot> {
  const requestScope = new AbortController();
  const cancel = () => requestScope.abort(signal?.reason);
  if (signal?.aborted) cancel();
  else signal?.addEventListener("abort", cancel, { once: true });
  const timeout = new Error("会话验证超时，请检查服务连接后重试");
  const deadline = setTimeout(() => requestScope.abort(timeout), sessionRequestTimeoutMs);
  try {
    const [mode, user] = await Promise.all([
      contractRequest(AuthenticationService.authenticationConfigApiV1AuthConfigGet(), requestScope.signal).then(
        (config) => {
          if (config.mode !== "local" && config.mode !== "oidc") throw new Error("身份配置返回了不支持的登录模式");
          return config.mode;
        },
      ),
      contractRequest(AuthenticationService.currentUserApiV1AuthMeGet(), requestScope.signal).catch(
        (error: unknown) => {
          if (error instanceof ApiError && error.status === 401) return null;
          throw error;
        },
      ),
    ]);
    return { mode, user };
  } catch (error) {
    if (requestScope.signal.reason === timeout) throw timeout;
    throw error;
  } finally {
    clearTimeout(deadline);
    signal?.removeEventListener("abort", cancel);
    // Failure must release its sibling; a retry owns entirely new requests.
    requestScope.abort();
  }
}

export function login(email: string, password: string): Promise<UserRead> {
  return contractRequest(
    AuthenticationService.loginApiV1AuthLoginPost({ requestBody: { email: email.trim(), password } }),
  );
}

export function logout(): Promise<void> {
  return contractRequest(AuthenticationService.logoutApiV1AuthLogoutPost());
}

export function updateCurrentUser(profile: UserProfileUpdate): Promise<UserRead> {
  return contractRequest(AuthenticationService.updateCurrentUserApiV1AuthMePatch({ requestBody: profile }));
}

export function changeCurrentUserPassword(password: UserPasswordChange): Promise<void> {
  return contractRequest(
    AuthenticationService.changeCurrentUserPasswordApiV1AuthMePasswordPost({ requestBody: password }),
  );
}

export function getSessionEntity(entityId: string, signal?: AbortSignal): Promise<EntityRead> {
  return contractRequest(EntitiesService.getEntityApiV1EntitiesEntityIdGet({ entityId }), signal);
}

export type SessionUser = UserRead;
export type SessionEntity = EntityRead;
