import { ExternalLink } from "lucide-react";
import { formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { NewsEventSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { newsText as t } from "../../lib/i18n/news";
import type { DossierEntityOpener } from "../EntityDossierView";
import { newsTypeLabel } from "./presentation";
export function NewsResearchTimeline({
  items,
  onOpenTypedEntity,
  onOpenDetail,
  onOpenProvenance,
}: {
  items: NewsEventSearchItemRead[];
  onOpenTypedEntity: DossierEntityOpener;
  onOpenDetail: (eventId: string) => void;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  useLocale();

  return (
    <section className="news-research-timeline" aria-label={t("研究发布时间线")}>
      {items.map((item) => (
        <article key={item.id}>
          <div className="news-timeline-date">
            <time dateTime={item.published_at ?? undefined}>{formatDate(item.published_at ?? "")}</time>
            <StatusBadge value={newsTypeLabel(item.event_type)} />
          </div>
          <div className="news-timeline-content">
            <header>
              <h3>
                <button className="news-timeline-title-button" type="button" onClick={() => onOpenDetail(item.id)}>
                  {item.title}
                </button>
              </h3>
              {item.venue ? <span>{item.venue}</span> : null}
            </header>
            {item.summary ? <p>{item.summary}</p> : null}
            <div className="news-timeline-links">
              {item.publisher_entity ? (
                <button
                  type="button"
                  onClick={() =>
                    onOpenTypedEntity(
                      item.publisher_entity?.entity_type ?? "organization",
                      item.publisher_entity?.id ?? "",
                    )
                  }
                >
                  {item.publisher_entity.name}
                </button>
              ) : null}
              {item.related_entities.map((entity) => (
                <button type="button" key={entity.id} onClick={() => onOpenTypedEntity(entity.entity_type, entity.id)}>
                  {entity.name}
                </button>
              ))}
            </div>
            <div className="news-timeline-actions">
              {item.canonical_url ? (
                <a href={item.canonical_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} />
                  {t("原始发布页")}
                </a>
              ) : null}
              <ProvenanceButton
                selection={{ resourceType: "news_event", resourceId: item.id, label: item.title }}
                onOpen={onOpenProvenance}
              />
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}
