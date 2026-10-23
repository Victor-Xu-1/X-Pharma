import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { geographyLabel, programOrganizations } from "./programPresentation";
import type { DrugEntityOpener, DrugProgram } from "./types";
import { organizationRoleLabels } from "./vocabulary";

export function ProgramOrganizationLinks({
  program,
  onOpenEntity,
}: {
  program: DrugProgram;
  onOpenEntity: DrugEntityOpener;
}) {
  const organizations = programOrganizations(program);
  if (!organizations.length) return <span>{t("未披露")}</span>;
  return (
    <span className="drug-program-entity-list">
      {organizations.map((organization) => (
        <span key={`${program.id}-${organization.entity_id}-${organization.role}`}>
          <button
            className="table-link-button"
            type="button"
            onClick={() => onOpenEntity("organization", organization.entity_id)}
          >
            {organization.name}
          </button>
          <small>
            {controlledDrugLabel(organization.role, organizationRoleLabels)}
            {organization.country_region ? ` · ${geographyLabel(organization.country_region)}` : ""}
            {organization.organization_type ? ` · ${organization.organization_type}` : ""}
          </small>
        </span>
      ))}
    </span>
  );
}
