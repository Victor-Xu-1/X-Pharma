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

export async function loadSession(signal?: AbortSignal): Promise<SessionSnapshot> {
  const [config, currentUser] = await Promise.allSettled([
    contractRequest(AuthenticationService.authenticationConfigApiV1AuthConfigGet(), signal),
    contractRequest(AuthenticationService.currentUserApiV1AuthMeGet(), signal),
  ]);
  if (config.status === "rejected") throw config.reason;
  const mode = config.value.mode;
  if (mode !== "local" && mode !== "oidc") throw new Error("身份配置返回了不支持的登录模式");
  if (currentUser.status === "fulfilled") return { mode, user: currentUser.value };
  if (currentUser.reason instanceof ApiError && currentUser.reason.status === 401) return { mode, user: null };
  throw currentUser.reason;
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
