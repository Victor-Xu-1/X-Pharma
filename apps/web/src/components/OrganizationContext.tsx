import { createContext, useContext } from "react";

export type OrganizationControls = {
  switchOrganization: (organizationId: string) => Promise<void>;
  organizationName?: string | null;
};
export const OrganizationContext = createContext<OrganizationControls | null>(null);
export const useOrganizationControls = () => useContext(OrganizationContext);
