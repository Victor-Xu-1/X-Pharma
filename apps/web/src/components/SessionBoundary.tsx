import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { ApiError } from "../lib/api";
import { switchOrganization as switchOrganizationRequest } from "../lib/contracts/organizations";
import { type AuthMode, loadSession, logout, type SessionSnapshot, sessionKeys } from "../lib/contracts/session";
import {
  hasPendingSessionWrites,
  setOrganizationSession,
  suspendOrganizationSession,
} from "../lib/organizationSession";
import type { User } from "../lib/types";
import { type WorkbenchKey, workbenchPath } from "../lib/workspaceRouting";
import { ErrorState, Spinner } from "./common";
import { LoginScreen } from "./LoginScreen";
import { OrganizationContext } from "./OrganizationContext";
import { SessionIdentityContext } from "./SessionIdentityContext";
import { WorkspaceQueryScope } from "./WorkspaceQueryScope";

export interface AuthenticatedSession {
  authMode: AuthMode;
  logout: () => void;
  logoutPending: boolean;
  logoutError: string | null;
  updateUser: (user: User) => void;
  user: User;
}

export function SessionBoundary({
  workbench,
  children,
}: {
  workbench: WorkbenchKey;
  children: (session: AuthenticatedSession) => ReactNode;
}) {
  const queryClient = useQueryClient();
  const unauthorizedProbe = useRef<Promise<void> | null>(null);
  const channel = useRef<BroadcastChannel | null>(null);
  const workspaceClient = useRef<QueryClient | null>(null);
  const bindWorkspaceClient = useCallback((client: QueryClient | null) => {
    workspaceClient.current = client;
  }, []);
  const [contextState, setContextState] = useState<"ready" | "checking" | "uncertain">("ready");
  const [contextNotice, setContextNotice] = useState("");
  const session = useQuery({
    queryKey: sessionKeys.current,
    queryFn: ({ signal }) => loadSession(signal),
    staleTime: Number.POSITIVE_INFINITY,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
  const user = session.data?.user ?? null;
  const authMode = session.data?.mode ?? "local";

  const clearSession = useCallback(() => {
    void workspaceClient.current?.cancelQueries();
    workspaceClient.current?.clear();
    setOrganizationSession(null);
    const mode = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current)?.mode ?? "local";
    queryClient.removeQueries({
      predicate: (query) =>
        query.queryKey.length !== sessionKeys.current.length ||
        query.queryKey.some((part, index) => part !== sessionKeys.current[index]),
    });
    queryClient.getMutationCache().clear();
    queryClient.setQueryData<SessionSnapshot>(sessionKeys.current, { mode, user: null });
  }, [queryClient]);

  const evictWorkspace = useCallback(async () => {
    await workspaceClient.current?.cancelQueries();
    workspaceClient.current?.clear();
    await queryClient.cancelQueries();
    queryClient.removeQueries({
      predicate: (query) =>
        query.queryKey !== sessionKeys.current &&
        JSON.stringify(query.queryKey) !== JSON.stringify(sessionKeys.current),
    });
    queryClient.getMutationCache().clear();
  }, [queryClient]);

  const confirmOrganizationContext = useCallback(async () => {
    setContextState("checking");
    suspendOrganizationSession();
    await evictWorkspace();
    try {
      const next = await loadSession();
      setOrganizationSession(next.user);
      queryClient.setQueryData(sessionKeys.current, next);
      window.history.replaceState(null, "", workbenchPath(workbench));
      setContextState("ready");
      return next;
    } catch {
      setContextState("uncertain");
      return null;
    }
  }, [evictWorkspace, queryClient, workbench]);

  const switchOrganization = useCallback(
    async (organizationId: string) => {
      if (
        hasPendingSessionWrites() ||
        workspaceClient.current?.isMutating() ||
        queryClient
          .getMutationCache()
          .getAll()
          .some((mutation) => mutation.state.status === "pending")
      ) {
        throw new Error("操作正在提交，请等待完成后再切换组织");
      }
      setContextState("checking");
      setContextNotice("");
      suspendOrganizationSession();
      await evictWorkspace();
      try {
        await switchOrganizationRequest(organizationId);
      } catch {
        // A lost response does not prove the server kept the old cookie/context.
        // Only an authenticated read may re-open the workspace, even after 4xx.
        const actual = await confirmOrganizationContext();
        if (actual?.user && actual.user.tenant_id !== organizationId) {
          setContextNotice("未完成组织切换；已重新确认当前会话，请打开组织菜单重试。");
        }
        channel.current?.postMessage({ type: "context-changed" });
        return;
      }
      await confirmOrganizationContext();
      channel.current?.postMessage({ type: "context-changed" });
    },
    [confirmOrganizationContext, evictWorkspace, queryClient],
  );
  const confirmSessionAfterUnauthorized = useCallback(() => {
    if (unauthorizedProbe.current) return;
    const probe = (async () => {
      try {
        // A single data request can be stale or lose its cookie during a navigation.
        // Confirm the session directly before evicting the user's cached workspace.
        const response = await fetch("/api/v1/auth/me", {
          cache: "no-store",
          credentials: "same-origin",
        });
        if (response.ok) {
          const refreshedUser = (await response.json()) as User;
          const current = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current);
          if (current?.user) {
            if (current.user.tenant_id !== refreshedUser.tenant_id || current.user.id !== refreshedUser.id) {
              await confirmOrganizationContext();
              return;
            }
            queryClient.setQueryData<SessionSnapshot>(sessionKeys.current, {
              mode: current.mode,
              user: refreshedUser,
            });
          }
          return;
        }
        if (response.status === 401 || response.status === 403) clearSession();
      } catch {
        // A transient probe failure does not prove that the human session is invalid.
      } finally {
        unauthorizedProbe.current = null;
      }
    })();
    unauthorizedProbe.current = probe;
  }, [clearSession, confirmOrganizationContext, queryClient]);
  const finishLogout = useCallback(() => {
    window.history.replaceState(null, "", workbenchPath(workbench));
    clearSession();
    channel.current?.postMessage({ type: "context-changed" });
  }, [clearSession, workbench]);
  const logoutRequest = useMutation({
    mutationFn: logout,
    onSuccess: finishLogout,
    onError: (error) => {
      if (error instanceof ApiError && error.status === 401) finishLogout();
    },
  });
  const updateUser = useCallback(
    (nextUser: User) => {
      const active = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current)?.user;
      if (active && (active.id !== nextUser.id || active.tenant_id !== nextUser.tenant_id)) {
        void confirmOrganizationContext();
        return;
      }
      queryClient.setQueryData<SessionSnapshot>(sessionKeys.current, (current) =>
        current ? { mode: current.mode, user: nextUser } : current,
      );
    },
    [confirmOrganizationContext, queryClient],
  );

  useLayoutEffect(() => {
    if (contextState === "ready") setOrganizationSession(user);
  }, [contextState, user]);

  useEffect(() => {
    const changed = () => void confirmOrganizationContext();
    window.addEventListener("pharma:context-changed", changed);
    if (typeof BroadcastChannel !== "undefined") {
      const activeChannel = new BroadcastChannel("x-pharma-session");
      channel.current = activeChannel;
      activeChannel.onmessage = (event: MessageEvent<unknown>) => {
        if (
          event.data &&
          typeof event.data === "object" &&
          "type" in event.data &&
          event.data.type === "context-changed"
        )
          changed();
      };
    }
    return () => {
      window.removeEventListener("pharma:context-changed", changed);
      channel.current?.close();
      channel.current = null;
      setOrganizationSession(null);
    };
  }, [confirmOrganizationContext]);

  useEffect(() => {
    const unauthorized = () => {
      const current = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current);
      if (current?.user) confirmSessionAfterUnauthorized();
    };
    window.addEventListener("pharma:unauthorized", unauthorized);
    window.addEventListener("focus", unauthorized);
    const visible = () => {
      if (document.visibilityState === "visible") unauthorized();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.removeEventListener("pharma:unauthorized", unauthorized);
      window.removeEventListener("focus", unauthorized);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [confirmSessionAfterUnauthorized, queryClient]);

  if (contextState !== "ready")
    return (
      <div className="session-loading">
        {contextState === "checking" ? (
          <Spinner label="正在确认组织会话" />
        ) : (
          <ErrorState
            message="组织会话尚未确认，已暂停工作台以保护数据隔离"
            retry={() => void confirmOrganizationContext()}
          />
        )}
      </div>
    );

  if (!session.data && !session.error) {
    return (
      <div className="session-loading">
        <Spinner label="正在验证会话" />
      </div>
    );
  }
  if (session.error && !session.data) {
    const message = session.error instanceof Error ? session.error.message : "会话验证失败";
    return (
      <div className="session-loading">
        <ErrorState message={message} retry={() => void session.refetch()} />
      </div>
    );
  }
  if (!user) {
    return (
      <LoginScreen
        mode={authMode}
        workbench={workbench}
        onLogin={(nextUser) => {
          logoutRequest.reset();
          queryClient.setQueryData(sessionKeys.current, { mode: authMode, user: nextUser });
        }}
      />
    );
  }

  return (
    <SessionIdentityContext value={user}>
      <OrganizationContext value={{ switchOrganization, organizationName: user.organization_name }}>
        {contextNotice ? (
          <p role="alert" className="form-error">
            {contextNotice}
          </p>
        ) : null}
        <WorkspaceQueryScope
          key={`${user.id}:${user.tenant_id}:${user.role}`}
          parent={queryClient}
          onClient={bindWorkspaceClient}
        >
          {children({
            authMode,
            user,
            logout: () => logoutRequest.mutate(),
            logoutPending: logoutRequest.isPending,
            logoutError: logoutRequest.isError ? "退出失败，请重试" : null,
            updateUser,
          })}
        </WorkspaceQueryScope>
      </OrganizationContext>
    </SessionIdentityContext>
  );
}
