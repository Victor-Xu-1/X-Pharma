import { ExternalLink, Landmark, ShieldCheck } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { Regulatory } from "../EntityDossierView";
import { governedDisplay } from "./programPresentation";
import type { DrugEntityOpener } from "./types";
import {
  approvalEventTypes,
  dosageFormLabels,
  jurisdictionLabels,
  lineOfTherapyLabels,
  regulatoryEventLabels,
  regulatoryStatusLabels,
  routeLabels,
} from "./vocabulary";

export function DrugRegulatory({
  data,
  onOpen,
  onOpenEntity,
  onOpenRegulatoryEvent,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
  onOpenRegulatoryEvent: (eventId: string) => void;
}) {
  const approvals = data.regulatory_events.filter((item) => approvalEventTypes.has(item.event_type));
  const otherEvents = data.regulatory_events.filter((item) => !approvalEventTypes.has(item.event_type));
  if (!data.regulatory_events.length) return <EmptyState title={t("暂无关联获批或监管事件")} />;

  return (
    <div className="drug-regulatory-view">
      <section className="drug-profile-section" aria-labelledby="drug-approvals-title">
        <header>
          <div>
            <span>{t("上市与适应症")}</span>
            <h3 id="drug-approvals-title">{t("获批适应症（{count}）", { count: approvals.length })}</h3>
          </div>
          <Landmark size={18} aria-hidden="true" />
        </header>
        {approvals.length ? (
          <ScrollableTableRegion ariaLabel={t("药物获批适应症")} className="drug-regulatory-table-region">
            <table aria-label={t("药物获批适应症")}>
              <thead>
                <tr>
                  <th>{t("适应症")}</th>
                  <th>{t("获批时间")}</th>
                  <th>{t("国家/地区")}</th>
                  <th>{t("审批类型")}</th>
                  <th>{t("获批人群与限定")}</th>
                  <th>{t("监管机构")}</th>
                  <th>{t("状态")}</th>
                  <th aria-label={t("操作")} />
                </tr>
              </thead>
              <tbody>
                {approvals.map((item) => {
                  const indication = item.indication_entity;
                  const qualifiers = [
                    item.line_of_therapy
                      ? t("治疗线次：{value}", { value: governedDisplay(item.line_of_therapy, lineOfTherapyLabels) })
                      : null,
                    item.biomarker ? t("生物标志物：{value}", { value: item.biomarker }) : null,
                    item.dosage_form
                      ? t("剂型：{value}", { value: governedDisplay(item.dosage_form, dosageFormLabels) })
                      : null,
                    item.route_of_administration
                      ? t("给药途径：{value}", { value: governedDisplay(item.route_of_administration, routeLabels) })
                      : null,
                  ].filter(Boolean);
                  return (
                    <tr key={item.id}>
                      <td>
                        {indication ? (
                          <button
                            className="table-link-button"
                            type="button"
                            onClick={() => onOpenEntity(indication.entity_type, indication.id)}
                          >
                            {indication.name}
                          </button>
                        ) : (
                          t("未披露")
                        )}
                      </td>
                      <td>{formatDate(item.decision_date)}</td>
                      <td>
                        {item.jurisdiction ? governedDisplay(item.jurisdiction, jurisdictionLabels) : t("未披露")}
                      </td>
                      <td>{controlledDrugLabel(item.event_type, regulatoryEventLabels)}</td>
                      <td className="drug-regulatory-population">
                        <strong>{item.approved_population ?? item.title}</strong>
                        {qualifiers.length ? <small>{qualifiers.join(" · ")}</small> : null}
                      </td>
                      <td>
                        {item.agency}
                        {item.application_number ? (
                          <small className="cell-subtitle">{item.application_number}</small>
                        ) : null}
                      </td>
                      <td>
                        <StatusBadge
                          value={item.status ?? item.event_type}
                          label={
                            item.status
                              ? controlledDrugLabel(item.status, regulatoryStatusLabels)
                              : controlledDrugLabel(item.event_type, regulatoryEventLabels)
                          }
                        />
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-button"
                            type="button"
                            title={t("打开监管事件详情")}
                            aria-label={t("打开监管事件详情：{title}", { title: item.title })}
                            onClick={() => onOpenRegulatoryEvent(item.id)}
                          >
                            <ExternalLink size={16} />
                          </button>
                          <ProvenanceButton
                            selection={{ resourceType: "regulatory_event", resourceId: item.id, label: item.title }}
                            onOpen={onOpen}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title={t("暂无已批准适应症")} detail={t("其他监管事件仍保留在下方时间线")} />
        )}
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-other-regulatory-title">
        <header>
          <div>
            <span>{t("申报、标签与安全")}</span>
            <h3 id="drug-other-regulatory-title">{t("其他监管事件（{count}）", { count: otherEvents.length })}</h3>
          </div>
          <ShieldCheck size={18} aria-hidden="true" />
        </header>
        {otherEvents.length ? (
          <Regulatory
            data={{ ...data, regulatory_events: otherEvents }}
            onOpen={onOpen}
            onOpenRegulatoryEvent={onOpenRegulatoryEvent}
          />
        ) : (
          <EmptyState title={t("暂无其他监管事件")} />
        )}
      </section>
    </div>
  );
}
