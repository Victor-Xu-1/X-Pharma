import { Building2 } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { eventTypeLabels, regulatoryStatusLabels } from "../../lib/regulatoryDisplay";
import type { DossierSectionProps } from "./types";

export function Regulatory({
  data,
  onOpen,
  onOpenRegulatoryEvent,
}: DossierSectionProps & { onOpenRegulatoryEvent: (eventId: string) => void }) {
  useLocale();
  if (!data.regulatory_events.length) return <EmptyState title={t("暂无关联监管事件")} />;
  return (
    <div className="entity-record-list">
      {data.regulatory_events.map((item) => (
        <article key={item.id}>
          <Building2 size={18} />
          <div>
            <span>
              {item.agency} · {item.jurisdiction} · {formatDate(item.decision_date)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenRegulatoryEvent(item.id)}
                aria-label={t("打开监管事件详情：{title}", { title: item.title })}
              >
                {item.title}
              </button>
            </h3>
            <p>{item.application_number ?? item.event_identifier}</p>
          </div>
          <StatusBadge
            value={item.status ?? item.event_type}
            label={
              item.status
                ? controlledDrugLabel(item.status, regulatoryStatusLabels)
                : controlledDrugLabel(item.event_type, eventTypeLabels)
            }
          />
          <ProvenanceButton
            selection={{ resourceType: "regulatory_event", resourceId: item.id, label: item.title }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
