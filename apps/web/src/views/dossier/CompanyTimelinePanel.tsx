import { ShieldCheck } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { CompanyTimelineResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { openDossierEntity } from "./navigation";
import { formatMoney } from "./presentation";
import type { DossierEntityOpener } from "./types";

export function CompanyTimelinePanel({
  timeline,
  loading,
  error,
  retry,
  note,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  timeline: CompanyTimelineResult | undefined;
  loading: boolean;
  error: Error | null;
  retry: () => void;
  note?: string;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
}) {
  useLocale();
  return (
    <section className="company-intelligence-section">
      <header>
        <div>
          <h3>{t("管线状态与交易公告")}</h3>
        </div>
        <small>{note}</small>
      </header>
      {loading && !timeline ? (
        <Spinner label={t("正在加载公司时间线")} />
      ) : error ? (
        <ErrorState message={error.message || t("公司时间线加载失败")} retry={retry} />
      ) : timeline?.items.length ? (
        <ol className="company-event-timeline">
          {timeline.items.map((event) => (
            <li key={event.id}>
              <time>{formatDate(event.occurred_at)}</time>
              <span className={`company-event-marker ${event.event_type}`} aria-hidden="true" />
              <div>
                <span>{event.event_type === "program_status" ? t("管线状态") : t("交易公告")}</span>
                <h4>{event.title}</h4>
                {event.program ? (
                  <p>
                    <button
                      type="button"
                      onClick={() =>
                        openDossierEntity(onOpenEntity, onOpenTypedEntity, "drug", event.program?.drug_entity_id ?? "")
                      }
                    >
                      {event.program.drug_name}
                    </button>
                    {event.program.target_entity_id && event.program.target_name ? (
                      <>
                        <span> · </span>
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(
                              onOpenEntity,
                              onOpenTypedEntity,
                              "target",
                              event.program?.target_entity_id ?? "",
                            )
                          }
                        >
                          {event.program.target_name}
                        </button>
                      </>
                    ) : null}
                    {event.program.disease_entity_id && event.program.disease_name ? (
                      <>
                        <span> · </span>
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(
                              onOpenEntity,
                              onOpenTypedEntity,
                              "disease",
                              event.program?.disease_entity_id ?? "",
                            )
                          }
                        >
                          {event.program.disease_name}
                        </button>
                      </>
                    ) : null}
                    {event.program.geography ? ` · ${event.program.geography}` : ""}
                  </p>
                ) : null}
                {event.deal ? (
                  <p>
                    {event.deal.party_entities.map((party, index) => (
                      <span key={party.id}>
                        {index > 0 ? " × " : ""}
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(onOpenEntity, onOpenTypedEntity, party.entity_type, party.id)
                          }
                        >
                          {party.name}
                        </button>
                      </span>
                    ))}
                    {event.deal.territory ? ` · ${event.deal.territory}` : ""}
                    {event.deal.total_potential_amount !== null
                      ? ` · ${t("潜在总额")} ${formatMoney(event.deal.total_potential_amount, event.deal.currency)}`
                      : ""}
                  </p>
                ) : null}
              </div>
              {event.program ? (
                <ProvenanceButton
                  selection={{
                    resourceType: "development_program",
                    resourceId: event.program.id,
                    label: event.program.drug_name,
                  }}
                  onOpen={onOpen}
                />
              ) : null}
              {event.deal ? (
                <ProvenanceButton
                  selection={{ resourceType: "deal", resourceId: event.deal.id, label: event.deal.name }}
                  onOpen={onOpen}
                />
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState title={t("暂无带日期的公司事件")} detail={t("当前管线状态或交易记录缺少可用于排序的明确日期")} />
      )}
      {timeline?.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </section>
  );
}
