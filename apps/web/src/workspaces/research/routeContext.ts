import type { User } from "../../lib/types";
import type { useResearchNavigation } from "./useResearchNavigation";

export type WorkspaceSessionProps = {
  user: User;
  onLogout: () => void;
  onUserUpdated: (user: User) => void;
  logoutPending: boolean;
  logoutError: string | null;
};

export type ResearchRouteContext = ReturnType<typeof useResearchNavigation> & WorkspaceSessionProps;
