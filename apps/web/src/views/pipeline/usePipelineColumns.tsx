import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { PipelineResultGrain } from "../../lib/contracts/pipeline";
import type { CompetitiveProgramRead } from "../../lib/generated";
import { useMessages } from "../../lib/i18n";
import { pipelineMessages } from "../../lib/i18n/pipeline";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedDevelopmentPhase, localizedProgramTag } from "../../lib/i18n/programVocabulary";
import { compactPhaseLabels as phaseLabels } from "../../lib/phasePresentation";
import { publicProgramTags } from "../../lib/programDisplay";
import { programStatusLabels } from "./filterLabels";
import {
  IndicationLinks,
  OrganizationLinks,
  pipelineMechanisms,
  pipelineModalities,
  TargetLinks,
} from "./ProgramCells";
import { ProgramClinicalSignals, ProgramDealSignals, ProgramRights } from "./ProgramSignalCells";
export function usePipelineColumns({
  onOpenDealsForDrug,
  onOpenDrug,
  openOrganization,
  openTarget,
  openDisease,
  onOpenTrialsForDrug,
  resultGrain,
}: {
  onOpenDealsForDrug: (id: string) => void;
  onOpenDrug: (id: string) => void;
  openOrganization: (id: string) => void;
  openTarget: (id: string) => void;
  openDisease: (id: string) => void;
  onOpenTrialsForDrug: (id: string) => void;
  resultGrain: PipelineResultGrain;
}) {
  const t = useMessages(pipelineMessages);
  return useMemo<ColumnDef<CompetitiveProgramRead, unknown>[]>(
    () => [
      {
        accessorKey: "drug_name",
        header: t("药物"),
        size: 170,
        cell: ({ row }) => {
          const tags = publicProgramTags(row.original.program_tags).map(localizedProgramTag);
          const aggregateSummary =
            resultGrain === "drug" && row.original.project_count && row.original.project_count > 1
              ? t("{count} 个研发项目", { count: row.original.project_count })
              : "";
          const subtitle = [...tags, aggregateSummary].filter(Boolean).join(" · ");
          return (
            <button
              className="entity-name-button"
              type="button"
              onClick={() => onOpenDrug(row.original.drug_entity_id)}
            >
              <strong>{row.original.drug_name}</strong>
              {subtitle ? <small className="cell-subtitle">{subtitle}</small> : null}
            </button>
          );
        },
      },
      {
        accessorKey: "target_name",
        header: t("靶点组合"),
        size: 180,
        cell: ({ row }) => <TargetLinks program={row.original} onOpen={openTarget} />,
      },
      {
        accessorKey: "disease_name",
        header: t("适应症"),
        size: 180,
        cell: ({ row }) => <IndicationLinks program={row.original} onOpen={openDisease} />,
      },
      {
        accessorKey: "organization_name",
        header: t("参与机构与角色"),
        size: 210,
        cell: ({ row }) => <OrganizationLinks program={row.original} onOpen={openOrganization} />,
      },
      {
        accessorKey: "modality",
        header: t("药物类型"),
        size: 125,
        cell: ({ row }) => pipelineModalities(row.original),
      },
      {
        accessorKey: "mechanism_of_action",
        header: t("作用机制"),
        size: 180,
        cell: ({ row }) => pipelineMechanisms(row.original),
      },
      {
        accessorKey: "phase",
        header: t("总体阶段"),
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? (
            <StatusBadge value={phaseLabels[value] ?? value} label={localizedDevelopmentPhase(value)} />
          ) : (
            <span>{t("未披露")}</span>
          );
        },
      },
      {
        accessorKey: "status_detail",
        header: t("项目状态"),
        size: 130,
        cell: ({ row }) => {
          // The badge only ever shows the governed vocabulary; ungoverned source text is
          // kept visible as detail instead of being rendered as if it were a known state.
          const governed = row.original.program_status;
          const detail = row.original.status_detail;
          if (!governed && !detail) return <span>{t("未披露")}</span>;
          return (
            <span className="domain-primary-cell">
              {governed ? (
                <StatusBadge
                  value={programStatusLabels[governed] ?? governed}
                  label={
                    programStatusLabels[governed]
                      ? professionalEnumLabel(programStatusLabels[governed], governed)
                      : governed
                  }
                />
              ) : (
                <span>{t("状态未记录")}</span>
              )}
              {detail && detail !== governed ? <small className="cell-subtitle">{detail}</small> : null}
            </span>
          );
        },
      },
      {
        accessorKey: "geography",
        header: t("记录地区"),
        size: 115,
        cell: ({ getValue }) => String(getValue() ?? t("未披露")),
      },
      {
        accessorKey: "global_phase",
        header: t("全球阶段"),
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? (
            <StatusBadge value={phaseLabels[value] ?? value} label={localizedDevelopmentPhase(value)} />
          ) : (
            <span>{t("未披露")}</span>
          );
        },
      },
      {
        accessorKey: "global_phase_started_at",
        header: t("全球阶段起始"),
        size: 130,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "china_phase",
        header: t("中国阶段"),
        size: 105,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return value ? (
            <StatusBadge value={phaseLabels[value] ?? value} label={localizedDevelopmentPhase(value)} />
          ) : (
            <span>{t("未披露")}</span>
          );
        },
      },
      {
        accessorKey: "china_phase_started_at",
        header: t("中国阶段起始"),
        size: 130,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "clinical_signals",
        header: t("临床信号"),
        size: 150,
        enableSorting: false,
        cell: ({ row }) => <ProgramClinicalSignals program={row.original} onOpen={onOpenTrialsForDrug} />,
      },
      {
        id: "deal_signals",
        header: t("交易信号"),
        size: 135,
        enableSorting: false,
        cell: ({ row }) => <ProgramDealSignals program={row.original} onOpen={onOpenDealsForDrug} />,
      },
      {
        id: "rights",
        header: t("权益地区"),
        size: 190,
        enableSorting: false,
        cell: ({ row }) => <ProgramRights program={row.original} />,
      },
      {
        id: "latest_milestone",
        header: t("最新里程碑"),
        size: 180,
        enableSorting: false,
        cell: ({ row }) => {
          const milestone = row.original.milestones?.at(-1);
          return milestone ? (
            <span className="table-stacked-copy">
              <span>{milestone.title}</span>
              <small>{formatDate(milestone.occurred_at)}</small>
            </span>
          ) : (
            <span>{t("未披露")}</span>
          );
        },
      },
      {
        accessorKey: "status_date",
        header: t("状态日期"),
        size: 120,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "traceability",
        header: t("来源"),
        size: 86,
        enableSorting: false,
        cell: ({ row }) =>
          row.original.source_document_id ? (
            <StatusBadge value="可追溯" label={t("可追溯")} />
          ) : (
            <span>{t("待补充")}</span>
          ),
      },
      {
        id: "open",
        header: t("档案"),
        size: 60,
        enableSorting: false,
        cell: ({ row }) => (
          <button
            className="icon-button"
            type="button"
            title={t("打开 {name} 档案", { name: row.original.drug_name })}
            aria-label={t("打开 {name} 档案", { name: row.original.drug_name })}
            onClick={() => onOpenDrug(row.original.drug_entity_id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [onOpenDealsForDrug, onOpenDrug, openOrganization, openTarget, openDisease, onOpenTrialsForDrug, resultGrain, t],
  );
}
