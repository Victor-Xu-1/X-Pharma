import { TrendingUp } from "lucide-react";
import { useMemo } from "react";
import { StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { EpidemiologyObservation } from "../../lib/contracts/epidemiology";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { useMessages } from "../../lib/i18n";
import { epidemiologyMessages } from "../../lib/i18n/epidemiology";
import type { DossierEntityOpener } from "../EntityDossierView";
import {
  comparableTrend,
  estimateLabel,
  measureValue,
  periodLabel,
  sexValue,
  type TrendSelection,
} from "./presentation";
export function useEpidemiologyColumns(
  openEpidemiologyEntity: DossierEntityOpener,
  onTrendChange: (selection: TrendSelection) => void,
  onOpenProvenance: (selection: ProvenanceSelection) => void,
) {
  const t = useMessages(epidemiologyMessages);
  return useMemo<ColumnDef<EpidemiologyObservation, unknown>[]>(
    () => [
      {
        id: "disease",
        accessorFn: (row) => row.disease_entity.name,
        header: t("疾病 / 人群"),
        size: 210,
        cell: ({ row }) => (
          <button
            className="entity-name-button"
            type="button"
            aria-label={row.original.disease_entity.name}
            onClick={() => openEpidemiologyEntity("disease", row.original.disease_entity.id)}
          >
            <strong>{row.original.disease_entity.name}</strong>
            <small
              className="cell-subtitle"
              title={row.original.patient_population?.target_entities.map((entity) => entity.name).join(", ")}
            >
              {row.original.patient_population?.name ?? row.original.population_scope}
            </small>
            {row.original.patient_population ? (
              <small className="cell-subtitle">
                {t("统计口径：{scope}", { scope: row.original.population_scope })}
              </small>
            ) : null}
          </button>
        ),
      },
      {
        id: "value",
        accessorFn: (row) => row.value,
        header: t("指标 / 估计值"),
        size: 175,
        cell: ({ row }) => (
          <span className="domain-primary-cell epidemiology-estimate">
            <StatusBadge value={measureValue(row.original.measure)} />
            <strong>{estimateLabel(row.original)}</strong>
            <small>{row.original.unit}</small>
          </span>
        ),
      },
      {
        accessorKey: "geography",
        header: t("地区"),
        size: 120,
      },
      {
        id: "demographic",
        header: t("年龄 / 性别"),
        size: 120,
        enableSorting: false,
        cell: ({ row }) => `${row.original.age_group ?? t("未标注")} / ${sexValue(row.original.sex)}`,
      },
      {
        id: "period_end",
        accessorFn: (row) => row.period_end,
        header: t("观察期"),
        size: 165,
        cell: ({ row }) => periodLabel(row.original),
      },
      {
        id: "publisher",
        accessorFn: (row) => row.publisher_entity?.name ?? null,
        header: t("发布机构"),
        size: 145,
        cell: ({ row }) =>
          row.original.publisher_entity ? (
            <button
              className="table-link-button"
              type="button"
              onClick={() =>
                openEpidemiologyEntity(
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
        accessorKey: "methodology",
        header: t("方法学"),
        size: 220,
        enableSorting: false,
        cell: ({ getValue }) => <span className="methodology-cell">{String(getValue() ?? t("未标注"))}</span>,
      },
      {
        id: "actions",
        header: t("操作"),
        size: 86,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="table-icon-actions">
            <button
              className="icon-button"
              type="button"
              title={t("查看同口径趋势")}
              aria-label={t("查看 {disease} 同口径趋势", { disease: row.original.disease_entity.name })}
              onClick={() => onTrendChange(comparableTrend(row.original))}
            >
              <TrendingUp size={16} />
            </button>
            <ProvenanceButton
              selection={{
                resourceType: "epidemiology_observation",
                resourceId: row.original.id,
                label: `${row.original.disease_entity.name} ${measureValue(row.original.measure)}`,
              }}
              onOpen={onOpenProvenance}
            />
          </span>
        ),
      },
    ],
    [openEpidemiologyEntity, onTrendChange, onOpenProvenance, t],
  );
}
