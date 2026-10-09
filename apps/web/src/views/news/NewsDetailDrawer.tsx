import { ExternalLink, FileText, X } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { entityLabels } from "../../lib/entityPresentation";
import type { NewsEventSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { newsText as t } from "../../lib/i18n/news";
import { useModalFocus } from "../../lib/useModalFocus";
import type { DossierEntityOpener } from "../EntityDossierView";
import { newsTypeLabel } from "./presentation";
import { SourceMetadata } from "../../components/SourceMetadata";
export function NewsDetailDrawer({
  data,
  loading,
  error,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenProvenance,
}: {
  data: NewsEventSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  useLocale();

  const dialogRef = useModalFocus<HTMLElement>(true, onClose);
  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label={t("关闭新闻事件详情")} onClick={onClose} />
      <aside
        ref={dialogRef}
        className="detail-drawer news-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="news-title"
        tabIndex={-1}
      >
        <header className="deal-detail-header">
          <div>
            {data?.event_identifier ? <span>{data.event_identifier}</span> : null}
            <h2 id="news-title">{data?.title ?? t("新闻事件详情")}</h2>
            {data ? (
              <div className="trial-detail-status">
                <StatusBadge value={newsTypeLabel(data.event_type)} />
                <span>{formatDate(data.published_at ?? "", true)}</span>
                <span>{data.venue ?? t("场景未披露")}</span>
              </div>
            ) : null}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label={t("关闭新闻事件详情")}
            data-modal-autofocus="true"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {loading ? (
          <Spinner label={t("正在加载新闻事件详情")} />
        ) : error ? (
          <ErrorState message={error.message || t("新闻事件详情加载失败")} retry={onRetry} />
        ) : data ? (
          <div className="drawer-content deal-detail-content news-detail-content">
            <section>
              <h3>{t("事件摘要")}</h3>
              <p>{data.summary || t("摘要未披露")}</p>
              <dl className="trial-detail-grid">
                <DetailValue term={t("语言")} value={data.language} />
                <DetailValue term={t("发布场景")} value={data.venue} />
              </dl>
            </section>
            <SourceMetadata details={data.details} />
            <section>
              <h3>{t("发布方与关联实体")}</h3>
              <div className="deal-detail-list">
                {data.publisher_entity ? (
                  <button
                    type="button"
                    onClick={() => {
                      const entityId = data.publisher_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.publisher_entity?.entity_type ?? "organization", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.publisher_entity.name}</strong>
                    <span>{t("发布方")}</span>
                  </button>
                ) : null}
                {data.related_entities.map((entity) => (
                  <button
                    key={entity.id}
                    type="button"
                    onClick={() => {
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(entity.entity_type, entity.id);
                        return;
                      }
                      onOpenEntity(entity.id);
                    }}
                  >
                    <strong>{entity.name}</strong>
                    <span>{entityLabels()[entity.entity_type] ?? entity.entity_type}</span>
                  </button>
                ))}
                {!data.publisher_entity && !data.related_entities.length ? <span>{t("暂无关联实体信息")}</span> : null}
              </div>
            </section>
            <section>
              <h3>{t("原始来源与证据")}</h3>
              {data.canonical_url ? (
                <a href={data.canonical_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={15} />
                  {t("打开原始发布页")}
                </a>
              ) : null}
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? t("来源文档已关联") : t("来源文档未关联")}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "news_event", resourceId: data.id, label: data.title }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || t("未披露")}</dd>
    </div>
  );
}
