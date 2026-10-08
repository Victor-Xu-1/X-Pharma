import { entityTypeLabel } from "../lib/entityPresentation";
import type { EntitySearchItemRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { entitySearchOptionText as t } from "../lib/i18n/entitySearchOption";
import { programModalityLabel } from "../lib/programDisplay";
import { isPublicEntityIdentifierNamespace } from "../lib/publicEntity";

const attributeLabels = {
  english_name: "英文名",
  innovation_type: "创新类型",
  modality: "药物类型",
  drug_category: "药品类别",
  organization_type: "机构类型",
  country_region: "国家/地区",
} as const;

const identifierNamespaceLabels: Record<string, string> = {
  cas: "CAS",
  chembl: "ChEMBL",
  hgnc: "HGNC",
  lei: "LEI",
  mesh: "MeSH",
  nct: "NCT",
  pubchem: "PubChem",
  uniprot: "UniProt",
};

function identifierNamespaceLabel(namespace: string): string {
  return identifierNamespaceLabels[namespace.trim().toLocaleLowerCase()] ?? namespace.trim().toLocaleUpperCase();
}

export function entityMatchExplanation(entity: EntitySearchItemRead): string | null {
  if (!entity.match) return null;
  if (
    entity.match.matched_value?.trim().toLocaleLowerCase() === entity.name.trim().toLocaleLowerCase() &&
    entity.match.match_type !== "external_id"
  ) {
    return null;
  }
  const relation = {
    exact: "精确匹配",
    partial: "部分匹配",
    semantic: "相关结果",
    related: "关联命中",
  } as const;
  const relationLabel = t(relation[entity.match.match_relation]);
  const source = {
    canonical_name: "名称",
    alias: "别名",
    external_id: "数据库编号",
    description: "简介",
    semantic: "相关内容",
    relationship: "已验证关联",
  } as const;
  const sourceLabel = t(source[entity.match.match_type]);
  const namespace =
    entity.match.namespace && isPublicEntityIdentifierNamespace(entity.match.namespace)
      ? `${identifierNamespaceLabel(entity.match.namespace)} · `
      : "";
  const value = entity.match.matched_value
    ? t("：{value}", { value: `${namespace}${entity.match.matched_value}` })
    : "";
  return t("{source}{relation}{value}", { source: sourceLabel, relation: relationLabel, value });
}

function entityIdentifier(entity: EntitySearchItemRead): string {
  const [namespace, value] = Object.entries(entity.external_ids)
    .filter(([candidate]) => isPublicEntityIdentifierNamespace(candidate))
    .sort(([left], [right]) => left.localeCompare(right))[0] ?? ["", ""];
  return value ? `${identifierNamespaceLabel(namespace)} · ${value}` : entityTypeLabel(entity);
}

function curatedAttributes(entity: EntitySearchItemRead): Array<[string, string]> {
  const entries: Array<[string, string]> = [];
  for (const [key, label] of Object.entries(attributeLabels)) {
    const value = entity.attributes[key];
    if ((typeof value === "string" || typeof value === "number") && String(value).trim()) {
      const displayValue = key === "modality" ? programModalityLabel(String(value)) : String(value).trim();
      entries.push([t(label), displayValue]);
    }
    if (entries.length === 3) break;
  }
  return entries;
}

export function EntitySearchOption({ entity }: { entity: EntitySearchItemRead }) {
  useLocale();
  const match = entityMatchExplanation(entity);
  const normalizedName = entity.name.trim().toLocaleLowerCase();
  const matchedAlias =
    entity.match?.match_type === "alias" ? entity.match.matched_value?.trim().toLocaleLowerCase() : null;
  const allAliases = (entity.aliases ?? []).filter((alias) => {
    const normalizedAlias = alias.trim().toLocaleLowerCase();
    return normalizedAlias !== matchedAlias && normalizedAlias !== normalizedName;
  });
  const aliases = allAliases.slice(0, 3);
  const remainingAliases = Math.max(0, allAliases.length - aliases.length);
  const attributes = curatedAttributes(entity);

  return (
    <span className="entity-search-candidate">
      <span className="entity-search-candidate-heading">
        <strong>{entity.name}</strong>
        <small>{entityIdentifier(entity)}</small>
      </span>
      {match ? <span className="entity-search-match">{match}</span> : null}
      {aliases.length ? (
        <span className="entity-search-aliases">
          {t("别名：{aliases}", { aliases: aliases.join(" / ") })}
          {remainingAliases ? ` / +${remainingAliases}` : ""}
        </span>
      ) : null}
      {attributes.length ? (
        <span className="entity-search-attributes">
          {attributes.map(([label, value]) => (
            <span key={label}>
              <b>{label}</b> {value}
            </span>
          ))}
        </span>
      ) : null}
    </span>
  );
}
