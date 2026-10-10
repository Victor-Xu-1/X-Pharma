import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { StatusBadge } from "../../components/common";
import { InlineEntityLinks } from "../../components/InlineEntityLinks";
import { PatentTimeline } from "../../components/PatentTimeline";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { PatentFamilySearchItemRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { patentMessages } from "../../lib/i18n/patents";
import { patentStatus } from "../../lib/patentDisplay";
import type { DossierEntityOpener } from "../EntityDossierView";
import { displayPatentList, patentCalendarDate, publicationNumbers } from "./presentation";

export function usePatentColumns(onPatentChange: (id: string | null) => void, openEntity: DossierEntityOpener) {
  const t = useMessages(patentMessages);
  return useMemo<ColumnDef<PatentFamilySearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "family_identifier",
        header: t("专利族与标题"),
        size: 285,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            aria-label={t("打开专利族详情：{identifier}", { identifier: row.original.family_identifier })}
            onClick={() => onPatentChange(row.original.id)}
          >
            <strong>{row.original.family_identifier}</strong>
            <small className="cell-subtitle">{row.original.title}</small>
          </button>
        ),
      },
      {
        accessorKey: "priority_date",
        header: t("最早优先权"),
        size: 105,
        cell: ({ getValue }) => patentCalendarDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "applicants",
        header: t("申请人"),
        size: 165,
        enableSorting: false,
        cell: ({ row }) => displayPatentList(row.original.applicants),
      },
      {
        accessorKey: "inventors",
        header: t("发明人"),
        size: 145,
        enableSorting: false,
        cell: ({ row }) => displayPatentList(row.original.inventors),
      },
      {
        accessorKey: "publications",
        header: t("公开文本"),
        size: 170,
        enableSorting: false,
        cell: ({ row }) => publicationNumbers(row.original.publications),
      },
      {
        accessorKey: "legal_status",
        header: t("法律状态"),
        size: 105,
        cell: ({ getValue }) => (
          <StatusBadge value={String(getValue() ?? "")} label={patentStatus(getValue() as string | null)} />
        ),
      },
      {
        accessorKey: "expiration_date",
        header: t("预计到期"),
        size: 105,
        cell: ({ getValue }) => patentCalendarDate(String(getValue() ?? "")),
      },
      {
        id: "timeline",
        header: t("事件与权利要求"),
        size: 190,
        enableSorting: false,
        cell: ({ row }) => <PatentTimeline patent={row.original} />,
      },
      {
        id: "linked_entities",
        header: t("关联实体"),
        size: 165,
        enableSorting: false,
        cell: ({ row }) => (
          <InlineEntityLinks
            label={t("{identifier} 的关联实体", { identifier: row.original.family_identifier })}
            items={row.original.linked_entities.map((entity) => ({ ...entity, key: entity.id, label: entity.name }))}
            onSelect={(entity) => openEntity(entity.entity_type, entity.id)}
          />
        ),
      },
      {
        id: "open",
        header: t("档案"),
        size: 55,
        enableSorting: false,
        cell: ({ row }) => (
          <button
            className="icon-button"
            type="button"
            title={t("打开 {identifier} 档案", { identifier: row.original.family_identifier })}
            aria-label={t("打开 {identifier} 档案", { identifier: row.original.family_identifier })}
            onClick={() => onPatentChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onPatentChange, openEntity, t],
  );
}
