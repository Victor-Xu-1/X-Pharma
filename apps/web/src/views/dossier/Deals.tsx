import { Landmark } from "lucide-react";
import { EmptyState, formatDate } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { dealTypeLabels, directionLabels, partyRoleLabels, phaseLabels } from "../../lib/dealDisplay";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { controlledDossierLabel } from "../../lib/i18n/dossierVocabulary";
import { openDossierEntity } from "./navigation";
import { formatMoney } from "./presentation";
import type { DossierEntityOpener, DossierSectionProps } from "./types";

export function Deals({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenDeal,
}: DossierSectionProps & {
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenDeal: (dealId: string) => void;
}) {
  useLocale();
  if (!data.deals.length) return <EmptyState title={t("暂无关联交易")} />;
  return (
    <div className="entity-record-list">
      {data.deals.map((item) => (
        <article key={item.id}>
          <Landmark size={18} />
          <div>
            <span>
              {controlledDossierLabel(item.deal_type, dealTypeLabels)} · {formatDate(item.announced_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenDeal(item.id)}
                aria-label={t("打开交易详情：{name}", { name: item.name })}
              >
                {item.name}
              </button>
            </h3>
            <p>
              {controlledDossierLabel(item.direction, directionLabels)} · {item.territory ?? t("地域条款未记录")} ·{" "}
              {t("潜在总额")} {formatMoney(item.total_potential_amount, item.currency)}
            </p>
            <div className="dossier-deal-links">
              <div>
                <span>{t("参与方")}</span>
                {item.party_roles.length || item.party_entities.length ? (
                  (item.party_roles.length ? item.party_roles : item.party_entities).map((party) => (
                    <button
                      key={`party-${item.id}-${party.id}`}
                      className="inline-link-button"
                      type="button"
                      onClick={() => openDossierEntity(onOpenEntity, onOpenTypedEntity, party.entity_type, party.id)}
                    >
                      {party.name}
                      {"role" in party && typeof party.role === "string"
                        ? ` · ${controlledDossierLabel(party.role, partyRoleLabels)}`
                        : ""}
                    </button>
                  ))
                ) : (
                  <small>{t("未披露")}</small>
                )}
              </div>
              <div>
                <span>{t("资产")}</span>
                {item.asset_stages.length || item.asset_entities.length ? (
                  (item.asset_stages.length ? item.asset_stages : item.asset_entities).map((asset) => (
                    <button
                      key={`asset-${item.id}-${asset.id}`}
                      className="inline-link-button"
                      type="button"
                      onClick={() => openDossierEntity(onOpenEntity, onOpenTypedEntity, asset.entity_type, asset.id)}
                    >
                      {asset.name}
                      {"current_development_phase" in asset && typeof asset.current_development_phase === "string"
                        ? ` · ${controlledDossierLabel(asset.current_development_phase, phaseLabels)}`
                        : ""}
                    </button>
                  ))
                ) : (
                  <small>{t("未披露")}</small>
                )}
              </div>
            </div>
          </div>
          <ProvenanceButton
            selection={{
              resourceType: "deal",
              resourceId: item.id,
              label: t("{type} 交易", { type: controlledDossierLabel(item.deal_type, dealTypeLabels) }),
            }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
