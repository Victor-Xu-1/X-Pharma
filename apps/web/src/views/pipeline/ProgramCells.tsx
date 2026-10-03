import type { CompetitiveProgramRead } from "../../lib/generated";
import { programModalityLabel } from "../../lib/programDisplay";

export const organizationRoleLabels: Record<string, string> = {
  originator: "原研方",
  collaborator: "合作方",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

export function EntityLink({
  entityId,
  name,
  onOpen,
}: {
  entityId: string | null;
  name: string | null;
  onOpen: (entityId: string) => void;
}) {
  if (!entityId || !name) return <span className="muted-text">未披露</span>;
  return (
    <button className="table-link-button" type="button" onClick={() => onOpen(entityId)}>
      {name}
    </button>
  );
}

export function TargetLinks({
  program,
  onOpen,
}: {
  program: CompetitiveProgramRead;
  onOpen: (entityId: string) => void;
}) {
  const targets = program.targets?.length
    ? program.targets
    : program.target_entity_id && program.target_name
      ? [{ entity_id: program.target_entity_id, name: program.target_name, role: "primary" as const, position: 0 }]
      : [];
  if (!targets.length) return <span className="muted-text">未披露</span>;
  return (
    <span className="target-link-list">
      {targets.map((target, index) => (
        <span key={target.entity_id}>
          {index ? <span aria-hidden="true"> + </span> : null}
          <button className="table-link-button" type="button" onClick={() => onOpen(target.entity_id)}>
            {target.name}
          </button>
        </span>
      ))}
    </span>
  );
}

export function OrganizationLinks({
  program,
  onOpen,
}: {
  program: CompetitiveProgramRead;
  onOpen: (entityId: string) => void;
}) {
  const organizations = program.organizations?.length
    ? program.organizations
    : program.organization_entity_id && program.organization_name
      ? [
          {
            entity_id: program.organization_entity_id,
            name: program.organization_name,
            role: "originator" as const,
            country_region: null,
            organization_type: null,
            position: 0,
          },
        ]
      : [];
  if (!organizations.length) return <span className="muted-text">未披露</span>;
  return (
    <span className="domain-primary-cell">
      {organizations.map((organization) => (
        <span className="target-link-list" key={`${organization.entity_id}-${organization.role}`}>
          <button className="table-link-button" type="button" onClick={() => onOpen(organization.entity_id)}>
            {organization.name}
          </button>
          <small className="cell-subtitle">
            {organizationRoleLabels[organization.role] ?? organization.role}
            {organization.country_region ? ` · ${organization.country_region}` : ""}
          </small>
        </span>
      ))}
    </span>
  );
}

function values(aggregated: string[] | undefined, single: string | null): string[] {
  return [
    ...new Set((aggregated?.length ? aggregated : single ? [single] : []).map((value) => value.trim()).filter(Boolean)),
  ];
}

export function pipelineModalities(program: CompetitiveProgramRead): string {
  return values(program.modalities, program.modality).map(programModalityLabel).join("、") || "--";
}

export function pipelineMechanisms(program: CompetitiveProgramRead): string {
  return values(program.mechanisms_of_action, program.mechanism_of_action).join("、") || "未披露";
}

export function IndicationLinks({
  program,
  onOpen,
}: {
  program: CompetitiveProgramRead;
  onOpen: (id: string) => void;
}) {
  const indications = program.indications?.length
    ? program.indications
    : [
        {
          disease_entity_id: program.disease_entity_id,
          disease_name: program.disease_name,
        },
      ];
  const unique = new Map<string, string>();
  for (const item of indications) {
    if (item.disease_entity_id && item.disease_name) unique.set(item.disease_entity_id, item.disease_name);
  }
  if (!unique.size) return <span className="muted-text">未披露</span>;
  return (
    <span className="domain-primary-cell">
      {[...unique].map(([id, name]) => (
        <EntityLink key={id} entityId={id} name={name} onOpen={onOpen} />
      ))}
    </span>
  );
}
