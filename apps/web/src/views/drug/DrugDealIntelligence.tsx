import { Landmark, ShieldCheck } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import {
  statusLabels as dealStatusLabels,
  dealTypeLabels,
  directionLabels,
  formatAmount,
  rightTypeLabels,
} from "../../lib/dealDisplay";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DossierEntityOpener } from "../EntityDossierView";
import { DrugDealActions } from "./DrugDealActions";
import { DrugDealAssets } from "./DrugDealAssets";
import { DrugDealParties } from "./DrugDealParties";
import { geographyLabel } from "./programPresentation";

export function DrugDealIntelligence({
  data,
  onOpen,
  onOpenDeal,
  onOpenEntity,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
  onOpenEntity: DossierEntityOpener;
}) {
  if (!data.deals.length) return <EmptyState title={t("暂无关联交易")} />;
  const rights = data.deals.flatMap((deal) => deal.rights.map((right) => ({ deal, right })));
  return (
    <div className="drug-deal-view">
      <section className="drug-profile-section" aria-labelledby="drug-linked-deals-title">
        <header>
          <div>
            <span>{t("交易与资产")}</span>
            <h3 id="drug-linked-deals-title">{t("关联交易（{count}）", { count: data.deals.length })}</h3>
          </div>
          <Landmark size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel={t("药物关联交易")} className="drug-deal-table-region">
          <table aria-label={t("药物关联交易")}>
            <thead>
              <tr>
                <th>{t("交易与披露")}</th>
                <th>{t("状态与方向")}</th>
                <th>{t("参与方与角色")}</th>
                <th>{t("资产与阶段")}</th>
                <th>{t("披露金额")}</th>
                <th>{t("地域与权益")}</th>
                <th>{t("信息更新")}</th>
                <th aria-label={t("操作")} />
              </tr>
            </thead>
            <tbody>
              {data.deals.map((deal) => (
                <tr key={deal.id}>
                  <td>
                    <button className="table-link-button" type="button" onClick={() => onOpenDeal(deal.id)}>
                      {deal.name}
                    </button>
                    <small className="cell-subtitle">
                      {controlledDrugLabel(deal.deal_type, dealTypeLabels)} · {formatDate(deal.announced_at)}
                    </small>
                  </td>
                  <td>
                    <StatusBadge value={deal.status} label={controlledDrugLabel(deal.status, dealStatusLabels)} />
                    <small className="cell-subtitle">{controlledDrugLabel(deal.direction, directionLabels)}</small>
                  </td>
                  <td>
                    <DrugDealParties deal={deal} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>
                    <DrugDealAssets deal={deal} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>
                    <span className="cell-stack">
                      <strong>
                        {t("首付款 {amount}", { amount: formatAmount(deal.upfront_amount, deal.currency) })}
                      </strong>
                      <small>
                        {t("潜在总额 {amount}", { amount: formatAmount(deal.total_potential_amount, deal.currency) })}
                      </small>
                    </span>
                  </td>
                  <td>
                    {deal.territory ? geographyLabel(deal.territory) : t("交易地域未披露")}
                    <small className="cell-subtitle">{t("{count} 条结构化权益", { count: deal.rights.length })}</small>
                  </td>
                  <td>{formatDate(deal.source_updated_at)}</td>
                  <td>
                    <DrugDealActions deal={deal} onOpen={onOpen} onOpenDeal={onOpenDeal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-deal-rights-title">
        <header>
          <div>
            <span>{t("持有人与地域")}</span>
            <h3 id="drug-deal-rights-title">{t("权益归属（{count}）", { count: rights.length })}</h3>
          </div>
          <ShieldCheck size={18} aria-hidden="true" />
        </header>
        {rights.length ? (
          <ScrollableTableRegion ariaLabel={t("药物交易权益归属")} className="drug-deal-rights-region">
            <table aria-label={t("药物交易权益归属")}>
              <thead>
                <tr>
                  <th>{t("权益持有人")}</th>
                  <th>{t("权益类型")}</th>
                  <th>{t("权益地区")}</th>
                  <th>{t("独占性")}</th>
                  <th>{t("范围说明")}</th>
                  <th>{t("关联交易")}</th>
                  <th aria-label={t("来源")} />
                </tr>
              </thead>
              <tbody>
                {rights.map(({ deal, right }) => (
                  <tr key={`${deal.id}-${right.id}`}>
                    <td>
                      <button
                        className="table-link-button"
                        type="button"
                        onClick={() => onOpenEntity("organization", right.holder_entity_id)}
                      >
                        {right.holder_name}
                      </button>
                    </td>
                    <td>{controlledDrugLabel(right.right_type, rightTypeLabels)}</td>
                    <td>{geographyLabel(right.territory)}</td>
                    <td>{right.exclusive == null ? t("未披露") : right.exclusive ? t("独占") : t("非独占")}</td>
                    <td>{right.scope_description ?? t("范围说明未披露")}</td>
                    <td>
                      <button className="table-link-button" type="button" onClick={() => onOpenDeal(deal.id)}>
                        {deal.name}
                      </button>
                    </td>
                    <td>
                      <ProvenanceButton
                        selection={{ resourceType: "deal", resourceId: deal.id, label: deal.name }}
                        onOpen={onOpen}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={t("当前关联交易未披露结构化地域权益")} />
        )}
      </section>
    </div>
  );
}
