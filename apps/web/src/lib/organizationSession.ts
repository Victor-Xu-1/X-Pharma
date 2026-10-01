type IdentityContext = { id: string; tenant_id: string };
let identity: IdentityContext | null = null;
let suspended = false;
let pendingWrites = 0;

export function hasPendingSessionWrites(): boolean {
  return pendingWrites > 0;
}

export function trackSessionWrite(method: string): () => void {
  if (["GET", "HEAD", "OPTIONS"].includes(method)) return () => {};
  pendingWrites += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    pendingWrites -= 1;
  };
}

export function setOrganizationSession(next: IdentityContext | null): void {
  identity = next;
  suspended = false;
}

export function suspendOrganizationSession(): void {
  suspended = true;
}

export function organizationHeaders(path: string, method = "GET"): Record<string, string> {
  if (
    (path === "/api/v1/auth/me" && method === "GET") ||
    [
      "/api/v1/auth/config",
      "/api/v1/auth/login",
      "/api/v1/auth/register",
      "/api/v1/auth/registration-policy",
      "/api/v1/auth/invitations/accept",
    ].includes(path) ||
    path.startsWith("/api/v1/auth/oidc/")
  )
    return {};
  if (suspended && path !== "/api/v1/auth/organizations/switch") {
    throw new Error("组织会话正在确认中，请稍后重试");
  }
  return identity ? { "X-Organization-ID": identity.tenant_id, "X-Account-ID": identity.id } : {};
}

export function notifySessionContext(response: Response): void {
  if (typeof window === "undefined") return;
  if (response.status === 401) window.dispatchEvent(new Event("pharma:unauthorized"));
  if (response.status === 409 && response.headers.get("X-Session-Context") === "changed") {
    window.dispatchEvent(new Event("pharma:context-changed"));
  }
}
