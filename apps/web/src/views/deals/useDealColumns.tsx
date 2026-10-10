import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import type { ColumnDef } from "../../components/VirtualDataTable";
import {
  dealLabel,
  dealTypeLabels,
  directionLabels,
  displayTerms,
  formatAmount,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../../lib/dealDisplay";
import type { DealSearchItemRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { dealMessages } from "../../lib/i18n/deals";
import type { DossierEntityOpener } from "../EntityDossierView";

export function useDealColumns(
  currency: string,
  onDealChange: (id: string | null) => void,
  openDealEntity: DossierEntityOpener,
) {
  const t = useMessages(dealMessages);
  return useMemo<ColumnDef<DealSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "name",
        header: t("交易名称"),
        size: 250,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onDealChange(row.original.id)}>
            <strong>{row.original.name}</strong>
            <small className="cell-subtitle">{displayTerms(row.original.terms)}</small>
          </button>
        ),
      },
      {
        accessorKey: "status",
        header: t("状态"),
        size: 88,
        cell: ({ getValue }) => (
          <StatusBadge value={String(getValue() ?? "")} label={dealLabel(String(getValue() ?? ""), statusLabels)} />
        ),
      },
      {
        accessorKey: "deal_type",
        header: t("类型"),
        size: 92,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "--");
          return <StatusBadge value={value} label={dealLabel(value, dealTypeLabels)} />;
        },
      },
      {
        accessorKey: "announced_at",
        header: t("初始披露"),
        size: 104,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "direction",
        header: t("方向"),
        size: 96,
        cell: ({ getValue }) => dealLabel(String(getValue() ?? ""), directionLabels),
      },
      {
        id: "parties",
        header: t("参与方与角色"),
        size: 220,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="deal-role-list">
            {row.original.party_roles.length
              ? row.original.party_roles.map((association) => (
                  <button
                    type="button"
                    key={`${association.id}-${association.role}`}
                    onClick={() => openDealEntity(association.entity_type, association.id)}
                  >
                    {association.name}
                    <small>{dealLabel(association.role, partyRoleLabels)}</small>
                  </button>
                ))
              : row.original.party_entities.map((entity) => (
                  <button type="button" key={entity.id} onClick={() => openDealEntity(entity.entity_type, entity.id)}>
                    {entity.name}
                    <small>{t("角色未披露")}</small>
                  </button>
                ))}
          </span>
        ),
      },
      {
        id: "assets",
        header: t("资产与交易时阶段"),
        size: 185,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="deal-role-list">
            {row.original.asset_stages.length
              ? row.original.asset_stages.map((asset) => (
                  <button type="button" key={asset.id} onClick={() => openDealEntity(asset.entity_type, asset.id)}>
                    {asset.name}
                    <small>
                      {asset.development_phase_at_transaction
                        ? dealLabel(asset.development_phase_at_transaction, phaseLabels)
                        : t("交易时阶段未披露")}
                      {asset.current_development_phase
                        ? t(" → 当前 {phase}", { phase: dealLabel(asset.current_development_phase, phaseLabels) })
                        : ""}
                    </small>
                  </button>
                ))
              : row.original.asset_entities.map((entity) => (
                  <button type="button" key={entity.id} onClick={() => openDealEntity(entity.entity_type, entity.id)}>
                    {entity.name}
                    <small>{t("交易阶段未披露")}</small>
                  </button>
                ))}
          </span>
        ),
      },
      {
        id: "rights",
        header: t("权益"),
        size: 175,
        enableSorting: false,
        cell: ({ row }) =>
          row.original.rights.length
            ? row.original.rights
                .slice(0, 2)
                .map((right) => `${dealLabel(right.right_type, rightTypeLabels)} · ${right.territory}`)
                .join(" / ")
            : t("未披露"),
      },
      {
        accessorKey: "territory",
        header: t("交易地域"),
        size: 105,
        cell: ({ getValue }) => String(getValue() ?? "--"),
      },
      {
        accessorKey: "upfront_amount",
        header: t("首付款"),
        size: 110,
        enableSorting: Boolean(currency),
        cell: ({ row }) => formatAmount(row.original.upfront_amount, row.original.currency),
      },
      {
        accessorKey: "total_potential_amount",
        header: t("潜在总额"),
        size: 115,
        enableSorting: Boolean(currency),
        cell: ({ row }) => formatAmount(row.original.total_potential_amount, row.original.currency),
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
            title={t("打开 {name} 实体档案", { name: row.original.name })}
            aria-label={t("打开 {name} 实体档案", { name: row.original.name })}
            onClick={() => onDealChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [currency, onDealChange, openDealEntity, t],
  );
}
