import { formatDate } from "../../components/common";
import { dealLabel, partyRoleLabels, phaseLabels } from "../../lib/dealDisplay";
import type { DealSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import type { DossierEntityOpener } from "../EntityDossierView";

export function DealParties({ data, onOpenEntity }: { data: DealSearchItemRead; onOpenEntity: DossierEntityOpener }) {
  useLocale();
  return (
    <section>
      <h3>{t("参与方角色")}</h3>
      <div className="deal-detail-list">
        {data.party_roles.length ? (
          sourceRecordRows(data.party_roles).map(({ value: association, key }) => (
            <button key={key} type="button" onClick={() => onOpenEntity(association.entity_type, association.id)}>
              <strong>{association.name}</strong>
              <span>{dealLabel(association.role, partyRoleLabels)}</span>
              <small>
                {[association.country_region, association.organization_type].filter(Boolean).join(" · ") ||
                  t("机构属性未披露")}
              </small>
            </button>
          ))
        ) : data.party_entities.length ? (
          sourceRecordRows(data.party_entities).map(({ value: entity, key }) => (
            <button key={key} type="button" onClick={() => onOpenEntity(entity.entity_type, entity.id)}>
              <strong>{entity.name}</strong>
              <span>{t("角色未披露")}</span>
            </button>
          ))
        ) : (
          <span>{t("参与方角色未披露")}</span>
        )}
      </div>
    </section>
  );
}

export function DealAssets({ data, onOpenEntity }: { data: DealSearchItemRead; onOpenEntity: DossierEntityOpener }) {
  useLocale();
  return (
    <section>
      <h3>{t("交易资产与阶段")}</h3>
      <div className="deal-detail-list">
        {data.asset_stages.length ? (
          sourceRecordRows(data.asset_stages).map(({ value: asset, key }) => (
            <button key={key} type="button" onClick={() => onOpenEntity(asset.entity_type, asset.id)}>
              <strong>{asset.name}</strong>
              <span>
                {asset.development_phase_at_transaction
                  ? dealLabel(asset.development_phase_at_transaction, phaseLabels)
                  : t("交易时阶段未披露")}
                {asset.current_development_phase
                  ? t(" → 当前 {phase}", { phase: dealLabel(asset.current_development_phase, phaseLabels) })
                  : ""}
              </span>
              <small>{t("当前阶段时点 {date}", { date: formatDate(asset.current_phase_as_of, true) })}</small>
            </button>
          ))
        ) : data.asset_entities.length ? (
          sourceRecordRows(data.asset_entities).map(({ value: entity, key }) => (
            <button key={key} type="button" onClick={() => onOpenEntity(entity.entity_type, entity.id)}>
              <strong>{entity.name}</strong>
              <span>{t("交易阶段未披露")}</span>
            </button>
          ))
        ) : (
          <span>{t("交易资产未披露")}</span>
        )}
      </div>
    </section>
  );
}
