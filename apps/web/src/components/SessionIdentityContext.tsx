import { createContext, useContext } from "react";

import type { User } from "../lib/types";

export const SessionIdentityContext = createContext<User | null>(null);
export const useSessionIdentity = () => useContext(SessionIdentityContext);
