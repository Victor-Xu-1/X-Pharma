import type { ReactNode } from "react";
import type { CollectionEntity } from "../lib/contracts/collections";
import type { DrugComparison, EntityDossier } from "../lib/contracts/entityDossier";
import { phaseLabels } from "../lib/dealDisplay";
import { formattingLocale } from "../lib/i18n";
import { type collectionMatrixMessages, collectionMatrixText as text } from "../lib/i18n/collectionMatrix";
import { professionalEnumLabel } from "../lib/i18n/professionalEnums";
import { isPublicEntityIdentifierNamespace } from "../lib/publicEntity";

type CoverageDomain = EntityDossier["coverage"][number]["domain"];

export const coverageRows: ReadonlyArray<{ domain: CoverageDomain; label: keyof typeof collectionMatrixMessages }> = [
  { domain: "relationships", label: "关联信息" },
  { domain: "evidence", label: "资料来源" },
  { domain: "activities", label: "生物活性" },
  { domain: "programs", label: "研发项目" },
  { domain: "clinical_trials", label: "临床试验" },
  { domain: "patents", label: "专利族" },
  { domain: "deals", label: "交易" },
  { domain: "regulatory_events", label: "监管事件" },
  { domain: "news_events", label: "资讯事件" },
  { domain: "structures", label: "化学结构" },
  { domain: "target_evidence", label: "靶点证据" },
];

const programStatusLabels = {
  active: "在研",
  inactive: "已停止",
  unknown: "暂未披露",
} as const;

const identifierLabels: Record<string, string> = {
  chembl: "ChEMBL",
  hgnc: "HGNC",
  uniprot: "UniProt",
  lei: "LEI",
};

export function externalIdentifiers(entity: CollectionEntity): string {
  const identifiers = Object.entries(entity.external_ids)
    .filter(([namespace]) => isPublicEntityIdentifierNamespace(namespace))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(
      ([namespace, value]) =>
        `${namespace === "nct" ? text("NCT 编号") : namespace === "patent_number" ? text("专利号") : (identifierLabels[namespace] ?? namespace.toLocaleUpperCase())} · ${value}`,
    );
  return identifiers.join(" · ") || text("未披露");
}

export function coverageValue(dossier: EntityDossier, domain: CoverageDomain): ReactNode {
  const coverage = dossier.coverage.find((item) => item.domain === domain);
  if (!coverage) return <span className="comparison-missing">{text("未提供")}</span>;
  if (coverage.status === "not_observed") {
    return (
      <span className="comparison-missing" title={coverage.note}>
        {text("未观察到")}
      </span>
    );
  }
  return (
    <span title={coverage.note}>
      <strong>{new Intl.NumberFormat(formattingLocale()).format(coverage.total)}</strong>
      {coverage.status === "truncated" ? (
        <small>
          {text("当前返回 {count}", { count: new Intl.NumberFormat(formattingLocale()).format(coverage.returned) })}
        </small>
      ) : null}
    </span>
  );
}

export function missingValue(): ReactNode {
  return <span className="comparison-missing">{text("未披露")}</span>;
}

export type DrugComparisonProfile = DrugComparison["items"][number];

export function summarizedValues(values: string[]): ReactNode {
  const unique = [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right, "zh-CN"),
  );
  if (!unique.length) return missingValue();
  const visible = unique.slice(0, 4);
  return (
    <span title={unique.join(formattingLocale() === "en-US" ? ", " : "、")}>
      {visible.join(formattingLocale() === "en-US" ? ", " : "、")}
      {unique.length > visible.length
        ? text(" 等 {count} 项", { count: new Intl.NumberFormat(formattingLocale()).format(unique.length) })
        : ""}
    </span>
  );
}

export function profileStatusSummary(profile: DrugComparisonProfile): ReactNode {
  const entries = Object.entries(profile.program_status_counts);
  if (!entries.length) return missingValue();
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([status, count]) => {
      const caption = Object.hasOwn(programStatusLabels, status)
        ? text(programStatusLabels[status as keyof typeof programStatusLabels])
        : status;
      const number = new Intl.NumberFormat(formattingLocale()).format(count);
      return formattingLocale() === "en-US" ? `${caption} (${number})` : `${caption}（${number}）`;
    })
    .join(" · ");
}

export function profilePhase(value: string | null | undefined): ReactNode {
  return value
    ? Object.hasOwn(phaseLabels, value)
      ? professionalEnumLabel(phaseLabels[value])
      : value
    : missingValue();
}
