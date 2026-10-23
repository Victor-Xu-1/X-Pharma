import { Newspaper } from "lucide-react";
import { EmptyState, formatDate } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { newsEventTypeLabels } from "../../lib/newsDisplay";
import type { DossierSectionProps } from "./types";

export function News({
  data,
  onOpen,
  onOpenNewsEvent,
}: DossierSectionProps & { onOpenNewsEvent: (eventId: string) => void }) {
  useLocale();
  if (!data.news_events.length) return <EmptyState title={t("暂无关联新闻或会议动态")} />;
  return (
    <div className="entity-record-list">
      {data.news_events.map((item) => (
        <article key={item.id}>
          <Newspaper size={18} />
          <div>
            <span>
              {controlledDrugLabel(item.event_type, newsEventTypeLabels)} · {formatDate(item.published_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenNewsEvent(item.id)}
                aria-label={t("打开新闻事件详情：{title}", { title: item.title })}
              >
                {item.title}
              </button>
            </h3>
            <p>{item.summary ?? item.venue ?? item.event_identifier}</p>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "news_event", resourceId: item.id, label: item.title }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}
