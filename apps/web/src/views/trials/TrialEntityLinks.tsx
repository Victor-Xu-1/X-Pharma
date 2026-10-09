import { InlineEntityLinks } from "../../components/InlineEntityLinks";
import type { ClinicalTrialSearchItemRead } from "../../lib/generated";
import { clinicalCaption } from "../../lib/i18n/clinical";
import type { TrialEntityOpener } from "./viewTypes";
import { trialRoleLabels } from "./vocabulary";
export function RoleEntityLinks({
  roles,
  acceptedRoles,
  onOpenEntity,
  compact = false,
  label,
}: {
  roles: ClinicalTrialSearchItemRead["entity_roles"];
  acceptedRoles: string[];
  onOpenEntity: TrialEntityOpener;
  compact?: boolean;
  label?: string;
}) {
  const items = (roles ?? []).filter((item) => acceptedRoles.includes(item.role));
  return (
    <InlineEntityLinks
      label={label ?? acceptedRoles.map((role) => clinicalCaption(trialRoleLabels[role])).join("与")}
      compact={compact}
      items={items.map((item) => ({
        ...item,
        key: `${item.role}-${item.entity_id}`,
        label: `${trialRoleLabels[item.role] ? clinicalCaption(trialRoleLabels[item.role]) : item.role}: ${item.name}`,
      }))}
      onSelect={(item) => onOpenEntity(item.entity_type, item.entity_id)}
    />
  );
}
