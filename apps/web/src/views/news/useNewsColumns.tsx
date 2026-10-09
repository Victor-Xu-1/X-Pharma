import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { NewsEventSearchItemRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { newsMessages } from "../../lib/i18n/news";
import type { DossierEntityOpener } from "../EntityDossierView";
import { newsTypeLabel } from "./presentation";
export function useNewsColumns(
  onNewsEventChange: (id: string) => void,
  openNewsEntity: DossierEntityOpener,
  setProvenanceSelection: (selection: ProvenanceSelection) => void,
) {
  const t = useMessages(newsMessages);

  return useMemo<ColumnDef<NewsEventSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "published_at",
        header: t("发布日期"),
        size: 108,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "title",
        header: t("标题与摘要"),
        size: 360,
        cell: ({ row }) => (
          <button
            className="entity-name-button domain-primary-cell"
            type="button"
            aria-label={t("打开新闻事件详情：{title}", { title: row.original.title })}
            onClick={() => onNewsEventChange(row.original.id)}
          >
            <strong>{row.original.title}</strong>
            <small>{row.original.summary ?? row.original.event_identifier}</small>
          </button>
        ),
      },
      {
        accessorKey: "event_type",
        header: t("类型"),
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "other");
          return <StatusBadge value={newsTypeLabel(value)} />;
        },
      },
      {
        id: "publisher",
        accessorFn: (row) => row.publisher_entity?.name ?? null,
        header: t("发布方"),
        size: 150,
        cell: ({ row }) =>
          row.original.publisher_entity ? (
            <button
              className="table-link-button"
              type="button"
              onClick={() =>
                openNewsEntity(
                  row.original.publisher_entity?.entity_type ?? "organization",
                  row.original.publisher_entity?.id ?? "",
                )
              }
            >
              {row.original.publisher_entity.name}
            </button>
          ) : (
            "--"
          ),
      },
      {
        id: "entities",
        header: t("关联对象"),
        size: 220,
        enableSorting: false,
        cell: ({ row }) =>
          row.original.related_entities.length ? (
            <span className="linked-entity-list">
              {row.original.related_entities.slice(0, 3).map((entity) => (
                <button
                  className="table-link-button"
                  type="button"
                  key={entity.id}
                  onClick={() => openNewsEntity(entity.entity_type, entity.id)}
                >
                  {entity.name}
                </button>
              ))}
              {row.original.related_entities.length > 3 ? (
                <small>+{row.original.related_entities.length - 3}</small>
              ) : null}
            </span>
          ) : (
            "--"
          ),
      },
      {
        accessorKey: "venue",
        header: t("会议 / 语言"),
        size: 125,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{row.original.venue ?? "--"}</strong>
            <small>{row.original.language ?? "--"}</small>
          </span>
        ),
      },
      {
        id: "source",
        header: t("来源"),
        size: 78,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-action-group">
            {row.original.canonical_url ? (
              <a
                className="icon-button"
                href={row.original.canonical_url}
                target="_blank"
                rel="noreferrer"
                title={t("打开原始发布页")}
                aria-label={t("打开 {title} 原始发布页", { title: row.original.title })}
              >
                <ExternalLink size={16} />
              </a>
            ) : null}
            <ProvenanceButton
              selection={{ resourceType: "news_event", resourceId: row.original.id, label: row.original.title }}
              onOpen={setProvenanceSelection}
            />
          </span>
        ),
      },
    ],
    [onNewsEventChange, openNewsEntity, setProvenanceSelection, t],
  );
}
