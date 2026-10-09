import { partyRoleLabels } from "../../lib/dealDisplay";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DossierEntityOpener } from "../EntityDossierView";
import { geographyLabel } from "./programPresentation";
import type { DrugDeal } from "./types";

export function DrugDealParties({ deal, onOpenEntity }: { deal: DrugDeal; onOpenEntity: DossierEntityOpener }) {
  if (!deal.party_roles.length && !deal.party_entities.length) return <span>{t("参与方未披露")}</span>;
  return (
    <span className="drug-deal-entity-list">
      {deal.party_roles.length
        ? deal.party_roles.map((party) => (
            <span key={`${deal.id}-${party.id}-${party.role}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(party.entity_type, party.id)}
              >
                {party.name}
              </button>
              <small>
                {controlledDrugLabel(party.role, partyRoleLabels)}
                {party.country_region ? ` · ${geographyLabel(party.country_region)}` : ""}
                {party.organization_type ? ` · ${party.organization_type}` : ""}
              </small>
            </span>
          ))
        : deal.party_entities.map((party) => (
            <span key={`${deal.id}-${party.id}-undisclosed`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(party.entity_type, party.id)}
              >
                {party.name}
              </button>
              <small>{t("角色未披露")}</small>
            </span>
          ))}
    </span>
  );
}
