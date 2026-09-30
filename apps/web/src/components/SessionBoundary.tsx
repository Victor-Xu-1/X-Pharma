import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useCallback, useEffect, useRef } from "react";

import { type AuthMode, loadSession, logout, type SessionSnapshot, sessionKeys } from "../lib/contracts/session";
import type { User } from "../lib/types";
import type { WorkbenchKey } from "../lib/workspaceRouting";
import { ErrorState, Spinner } from "./common";
import { LoginScreen } from "./LoginScreen";

export interface AuthenticatedSession {
  authMode: AuthMode;
  logout: () => void;
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
  const session = useQuery({
    queryKey: sessionKeys.current,
    queryFn: ({ signal }) => loadSession(signal),
  });
  const user = session.data?.user ?? null;
  const authMode = session.data?.mode ?? "local";

  const clearSession = useCallback(() => {
    const mode = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current)?.mode ?? "local";
    queryClient.removeQueries({
      predicate: (query) =>
        query.queryKey.length !== sessionKeys.current.length ||
        query.queryKey.some((part, index) => part !== sessionKeys.current[index]),
    });
    queryClient.getMutationCache().clear();
    queryClient.setQueryData<SessionSnapshot>(sessionKeys.current, { mode, user: null });
  }, [queryClient]);
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
  }, [clearSession, queryClient]);
  const logoutRequest = useMutation({ mutationFn: logout, onSettled: clearSession });
  const updateUser = useCallback(
    (nextUser: User) => {
      queryClient.setQueryData<SessionSnapshot>(sessionKeys.current, (current) =>
        current ? { mode: current.mode, user: nextUser } : current,
      );
    },
    [queryClient],
  );

  useEffect(() => {
    const unauthorized = () => {
      const current = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current);
      if (current?.user) confirmSessionAfterUnauthorized();
    };
    window.addEventListener("pharma:unauthorized", unauthorized);
    return () => window.removeEventListener("pharma:unauthorized", unauthorized);
  }, [confirmSessionAfterUnauthorized, queryClient]);

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
        onLogin={(nextUser) => queryClient.setQueryData(sessionKeys.current, { mode: authMode, user: nextUser })}
      />
    );
  }

  return children({
    authMode,
    user,
    logout: () => logoutRequest.mutate(),
    updateUser,
  });
}
