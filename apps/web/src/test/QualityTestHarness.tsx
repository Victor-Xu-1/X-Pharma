import { QualityOperationsPanel } from "../components/QualityOperationsPanel";
import { useQualityDrafts } from "../components/quality/useQualityDrafts";
import { SessionIdentityContext } from "../components/SessionIdentityContext";
import type { User } from "../lib/types";
import { useGovernanceActivity } from "../views/governance/useGovernanceActivity";
export const qualityControlledAdmin: User = {
  id: "controlled-actor",
  role: "admin",
  tenant_id: "controlled-tenant",
  display_name: "Controlled administrator",
  email: "controlled@example.invalid",
  phone: null,
  avatar_url: null,
};
export function QualityTestHarness({ user = null }: { user?: User | null }) {
  const activity = useGovernanceActivity();
  const draftState = useQualityDrafts();
  return (
    <SessionIdentityContext value={user}>
      <QualityOperationsPanel activity={activity} ready draftState={draftState} />
    </SessionIdentityContext>
  );
}
