import { formatDate } from "../../components/common";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../../lib/i18n/programVocabulary";
import type { DossierEntityOpener } from "../EntityDossierView";
import type { DrugDeal } from "./types";

export function DrugDealAssets({ deal, onOpenEntity }: { deal: DrugDeal; onOpenEntity: DossierEntityOpener }) {
  if (!deal.asset_stages.length && !deal.asset_entities.length) return <span>{t("交易资产未披露")}</span>;
  return (
    <span className="drug-deal-entity-list">
      {deal.asset_stages.length
        ? deal.asset_stages.map((asset) => (
            <span key={`${deal.id}-${asset.id}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(asset.entity_type, asset.id)}
              >
                {asset.name}
              </button>
              <small>
                {t("交易时 {phase}", { phase: phaseLabel(asset.development_phase_at_transaction) })}
                {asset.current_development_phase
                  ? ` · ${t("当前 {phase}", { phase: phaseLabel(asset.current_development_phase) })}`
                  : ""}
                {asset.current_phase_as_of ? ` · ${formatDate(asset.current_phase_as_of)}` : ""}
              </small>
            </span>
          ))
        : deal.asset_entities.map((asset) => (
            <span key={`${deal.id}-${asset.id}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(asset.entity_type, asset.id)}
              >
                {asset.name}
              </button>
              <small>{t("交易时阶段未披露")}</small>
            </span>
          ))}
    </span>
  );
}
