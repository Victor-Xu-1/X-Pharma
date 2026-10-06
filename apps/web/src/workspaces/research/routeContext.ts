import type { AuthMode } from "../../lib/contracts/session";
import type { User } from "../../lib/types";
import type { useResearchNavigation } from "./useResearchNavigation";

export type WorkspaceSessionProps = {
  user: User;
  authMode?: AuthMode;
  onLogout: () => void;
  onUserUpdated: (user: User) => void;
  logoutPending: boolean;
  logoutError: string | null;
};

export type ResearchRouteContext = ReturnType<typeof useResearchNavigation> & WorkspaceSessionProps;
