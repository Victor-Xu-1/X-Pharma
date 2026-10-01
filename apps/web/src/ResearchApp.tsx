import { SessionBoundary } from "./components/SessionBoundary";
import { ResearchWorkspace } from "./workspaces/research/ResearchWorkspace";

export function ResearchApp() {
  return (
    <SessionBoundary workbench="research">
      {({ user, logout, updateUser, logoutPending, logoutError }) => (
        <ResearchWorkspace
          user={user}
          onLogout={logout}
          onUserUpdated={updateUser}
          logoutPending={logoutPending}
          logoutError={logoutError}
        />
      )}
    </SessionBoundary>
  );
}
