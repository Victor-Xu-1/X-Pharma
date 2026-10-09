import { ExternalLink } from "lucide-react";
import { useMemo } from "react";
import { formatDate, StatusBadge } from "../../components/common";
import { InlineEntityLinks } from "../../components/InlineEntityLinks";
import type { ColumnDef } from "../../components/VirtualDataTable";
import type { ClinicalTrialSearchItemRead, TrialResultEvaluation } from "../../lib/generated";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { clinicalCaption, clinicalMessages } from "../../lib/i18n/clinical";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../../lib/i18n/trialVocabulary";
import {
  trialInitiationTypeLabels as initiationTypeLabels,
  trialResultEvaluationLabels as resultEvaluationLabels,
  trialTherapyLineLabels as therapyLineLabels,
} from "../../lib/trialFilters";
import { displayList, objectNames, primaryOutcomeSummary } from "./presentation";
import { RoleEntityLinks } from "./TrialEntityLinks";
import type { TrialEntityOpener } from "./viewTypes";
import { disclosureTypeLabels } from "./vocabulary";
export function useTrialColumns(openTrialEntity: TrialEntityOpener, onTrialChange: (id: string | null) => void) {
  const t = useMessages(clinicalMessages);
  return useMemo<ColumnDef<ClinicalTrialSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "registry_id",
        header: t("注册号与试验"),
        size: 260,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onTrialChange(row.original.id)}>
            <strong>{row.original.registry_id}</strong>
            <small className="cell-subtitle">{row.original.official_title}</small>
          </button>
        ),
      },
      {
        accessorKey: "acronym",
        header: t("试验简称"),
        size: 130,
        cell: ({ getValue }) => String(getValue() ?? "--"),
      },
      {
        accessorKey: "initiation_type",
        header: t("发起类型"),
        size: 150,
        cell: ({ getValue }) =>
          initiationTypeLabels[String(getValue() ?? "")]
            ? professionalEnumLabel(initiationTypeLabels[String(getValue() ?? "")], String(getValue()))
            : String(getValue() ?? "--"),
      },
      {
        accessorKey: "therapy_lines",
        header: t("治疗线次"),
        size: 150,
        enableSorting: false,
        cell: ({ row }) =>
          displayList(
            row.original.therapy_lines.map((value) =>
              therapyLineLabels[value] ? professionalEnumLabel(therapyLineLabels[value], value) : value,
            ),
            "--",
            3,
          ),
      },
      {
        id: "primary_outcome",
        header: t("报告终点"),
        size: 220,
        enableSorting: false,
        cell: ({ row }) => primaryOutcomeSummary(row.original),
      },
      {
        accessorKey: "has_results",
        header: t("结果"),
        size: 82,
        cell: ({ getValue }) => (
          <StatusBadge value={getValue() ? "已发布" : "未发布"} label={getValue() ? t("已发布") : t("未发布")} />
        ),
      },
      {
        accessorKey: "result_evaluation",
        header: t("最优评价"),
        size: 96,
        cell: ({ getValue }) => {
          const value = getValue() as TrialResultEvaluation | null;
          return value ? (
            <StatusBadge
              value={value}
              label={
                resultEvaluationLabels[value] ? professionalEnumLabel(resultEvaluationLabels[value], value) : value
              }
            />
          ) : (
            <span>{t("未评价")}</span>
          );
        },
      },
      {
        accessorKey: "phases",
        header: t("分期"),
        size: 90,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.phases.map(localizedTrialPhase)),
      },
      {
        accessorKey: "overall_status",
        header: t("状态"),
        size: 110,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "UNKNOWN");
          return <StatusBadge value={value} label={localizedTrialStatus(value)} />;
        },
      },
      {
        accessorKey: "conditions",
        header: t("适应症/疾病"),
        size: 150,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.conditions),
      },
      {
        id: "drug_roles",
        header: t("试验/联用药物"),
        size: 180,
        enableSorting: false,
        cell: ({ row }) => (
          <RoleEntityLinks
            roles={row.original.entity_roles}
            acceptedRoles={["investigational_drug", "combination_drug"]}
            onOpenEntity={openTrialEntity}
            compact
            label={t("{registry} 的药物关联", { registry: row.original.registry_id })}
          />
        ),
      },
      {
        id: "target_roles",
        header: t("试验/联用靶点"),
        size: 180,
        enableSorting: false,
        cell: ({ row }) => (
          <RoleEntityLinks
            roles={row.original.entity_roles}
            acceptedRoles={["investigational_target", "combination_target"]}
            onOpenEntity={openTrialEntity}
            compact
            label={t("{registry} 的靶点关联", { registry: row.original.registry_id })}
          />
        ),
      },
      {
        accessorKey: "key_result_count",
        header: t("关键结果"),
        size: 90,
        enableSorting: false,
        cell: ({ getValue }) => {
          const count = Number(getValue() ?? 0);
          return <StatusBadge value={String(count)} label={t("{count} 项", { count })} />;
        },
      },
      {
        accessorKey: "latest_result_disclosure",
        header: t("最近披露"),
        size: 190,
        enableSorting: false,
        cell: ({ getValue }) => {
          const disclosure = getValue() as ClinicalTrialSearchItemRead["latest_result_disclosure"];
          if (!disclosure) return "--";
          return (
            <span className="cell-stack">
              <strong>
                {disclosureTypeLabels[disclosure.disclosure_type]
                  ? clinicalCaption(disclosureTypeLabels[disclosure.disclosure_type])
                  : disclosure.disclosure_type}
              </strong>
              <small>{formatDate(disclosure.disclosed_at)}</small>
              {disclosure.external_id ? <small>{disclosure.external_id}</small> : null}
            </span>
          );
        },
      },
      {
        accessorKey: "interventions",
        header: t("干预措施"),
        size: 130,
        enableSorting: false,
        cell: ({ row }) => objectNames(row.original.interventions),
      },
      {
        accessorKey: "sponsors",
        header: t("申办方"),
        size: 140,
        enableSorting: false,
        cell: ({ row }) => objectNames(row.original.sponsors),
      },
      {
        accessorKey: "enrollment",
        header: t("入组"),
        size: 80,
        cell: ({ getValue }) => (getValue() == null ? "--" : Number(getValue()).toLocaleString(formattingLocale())),
      },
      {
        accessorKey: "study_type",
        header: t("研究类型"),
        size: 100,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return localizedTrialStudyType(value);
        },
      },
      {
        accessorKey: "last_update_posted",
        header: t("最近更新"),
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "linked_entities",
        header: t("关联实体"),
        size: 165,
        enableSorting: false,
        cell: ({ row }) => (
          <InlineEntityLinks
            label={t("{registry} 的关联实体", { registry: row.original.registry_id })}
            items={row.original.linked_entities.map((entity) => ({ ...entity, key: entity.id, label: entity.name }))}
            onSelect={(entity) => openTrialEntity(entity.entity_type, entity.id)}
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
            title={t("查看 {registry} 试验详情", { registry: row.original.registry_id })}
            aria-label={t("查看 {registry} 试验详情", { registry: row.original.registry_id })}
            onClick={() => onTrialChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [openTrialEntity, onTrialChange, t],
  );
}
