import { SessionBoundary } from "./components/SessionBoundary";
import { ResearchWorkspace } from "./workspaces/research/ResearchWorkspace";

export function ResearchApp() {
  return (
    <SessionBoundary workbench="research">
      {({ authMode, user, logout, updateUser, logoutPending, logoutError }) => (
        <ResearchWorkspace
          user={user}
          authMode={authMode}
          onLogout={logout}
          onUserUpdated={updateUser}
          logoutPending={logoutPending}
          logoutError={logoutError}
        />
      )}
    </SessionBoundary>
  );
}
