import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { RegulatoryEventSearchItemRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { regulatoryMessages } from "../../lib/i18n/regulatory";
import {
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetyStatusLabels,
  severityLabels,
} from "../../lib/regulatoryDisplay";
import type { DossierEntityOpener } from "../EntityDossierView";
import { regulatoryValue as displayValue } from "./presentation";
export function useRegulatoryColumns(onEventChange: (id: string) => void, openRegulatoryEntity: DossierEntityOpener) {
  const t = useMessages(regulatoryMessages);
  const columns = useMemo<ColumnDef<RegulatoryEventSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "title",
        header: t("监管事件"),
        size: 280,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onEventChange(row.original.id)}>
            <strong>{row.original.title}</strong>
            <small>{row.original.event_identifier}</small>
          </button>
        ),
      },
      {
        accessorKey: "decision_date",
        header: t("决定日期"),
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "agency",
        accessorFn: (row) => row.agency,
        header: t("机构 / 辖区"),
        size: 120,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{row.original.agency}</strong>
            <small>{row.original.jurisdiction}</small>
          </span>
        ),
      },
      {
        accessorKey: "event_type",
        header: t("事件类型"),
        size: 110,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "--");
          return <StatusBadge value={displayValue(value, eventTypeLabels)} />;
        },
      },
      {
        id: "designation",
        header: t("认定 / 标签"),
        size: 155,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{displayValue(row.original.designation_type, designationLabels)}</strong>
            <small>
              {displayValue(row.original.label_change_type, labelChangeLabels)}
              {row.original.label_version ? ` · ${row.original.label_version}` : ""}
            </small>
          </span>
        ),
      },
      {
        id: "safety",
        header: t("安全信号"),
        size: 175,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            <strong>{displayValue(row.original.safety_term)}</strong>
            <small>
              {displayValue(row.original.safety_severity, severityLabels)} ·{" "}
              {displayValue(row.original.safety_status, safetyStatusLabels)}
            </small>
          </span>
        ),
      },
      {
        id: "subject",
        accessorFn: (row) => row.subject_entity.name,
        header: t("药物 / 产品"),
        size: 145,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            onClick={() =>
              openRegulatoryEntity(row.original.subject_entity.entity_type, row.original.subject_entity.id)
            }
          >
            <strong>{row.original.subject_entity.name}</strong>
            <small>{row.original.application_number ?? t("申请号未披露")}</small>
          </button>
        ),
      },
      {
        id: "indication",
        header: t("适应症 / 人群"),
        size: 175,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="domain-primary-cell">
            {row.original.indication_entity ? (
              <button
                className="table-link-button"
                type="button"
                onClick={() =>
                  openRegulatoryEntity(
                    row.original.indication_entity?.entity_type ?? "disease",
                    row.original.indication_entity?.id ?? "",
                  )
                }
              >
                {row.original.indication_entity.name}
              </button>
            ) : (
              <strong>{t("未关联适应症")}</strong>
            )}
            <small>{row.original.approved_population ?? row.original.affected_population ?? t("人群未披露")}</small>
          </span>
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
            title={t("打开 {name} 档案", { name: row.original.subject_entity.name })}
            aria-label={t("打开 {name} 档案", { name: row.original.subject_entity.name })}
            onClick={() =>
              openRegulatoryEntity(row.original.subject_entity.entity_type, row.original.subject_entity.id)
            }
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onEventChange, openRegulatoryEntity, t],
  );
  return columns;
}
