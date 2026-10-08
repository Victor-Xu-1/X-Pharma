import type { IntelligenceEntity } from "./contracts/intelligence";
import { entityText as t } from "./i18n/entity";
import { getLocale, type Locale } from "./i18n/locale";
import { isPublicEntityIdentifierNamespace } from "./publicEntity";
import type { Entity } from "./types";

const entityLabelKeys = {
  target: "靶点",
  drug: "药物",
  organization: "机构",
  disease: "疾病",
  clinical_trial: "临床试验",
  patent: "专利",
  transaction: "交易",
  product: "产品",
  technology: "技术",
  person: "人物",
} as const;

export function entityLabels(locale: Locale = getLocale()): Record<string, string> {
  return Object.fromEntries(Object.entries(entityLabelKeys).map(([key, label]) => [key, t(label, {}, locale)]));
}

const relationshipLabels = {
  has_target: "作用靶点",
  has_competitor: "竞品关系",
  has_target_class: "靶点分类",
  has_indication: "关联适应症",
  developed_by: "研发机构",
  trial_studies_condition: "登记研究条件",
  trial_lead_sponsor: "登记主申办方",
  trial_collaborator: "登记合作方",
} as const;

export function relationshipLabel(predicate: string): string {
  return Object.hasOwn(relationshipLabels, predicate)
    ? t(relationshipLabels[predicate as keyof typeof relationshipLabels])
    : predicate;
}

type EntityIdentity = Pick<Entity, "entity_type" | "attributes">;

export function isProviderLabel(entity: EntityIdentity): boolean {
  return (
    ["disease", "organization"].includes(entity.entity_type) && entity.attributes.identity_scope === "provider_label"
  );
}

export function entityTypeLabel(entity: EntityIdentity): string {
  if (isProviderLabel(entity)) return entity.entity_type === "disease" ? t("登记条件") : t("登记申办方");
  const labels = entityLabels();
  return Object.hasOwn(labels, entity.entity_type) ? labels[entity.entity_type] : entity.entity_type;
}

export function entityIdentityNote(entity: EntityIdentity): string | null {
  if (!isProviderLabel(entity)) return null;
  const note = entity.attributes.identity_note;
  if (typeof note === "string" && note.trim()) return note;
  return entity.entity_type === "disease"
    ? t("注册平台的研究条件名称，尚未完成本体标准化，不代表获批适应症。")
    : t("注册平台的申办方名称，不代表已核实的法律主体或企业集团归并。");
}

export function publicIdentifiers(entity: IntelligenceEntity | Entity): Array<[string, string]> {
  const identifiers: Array<[string, string]> = [];
  const seen = new Set<string>();
  const add = (namespace: string, value: string) => {
    if (!isPublicEntityIdentifierNamespace(namespace)) return;
    const normalized = `${namespace.trim().toLocaleLowerCase()}:${value.trim().toLocaleLowerCase()}`;
    if (!namespace.trim() || !value.trim() || seen.has(normalized)) return;
    seen.add(normalized);
    identifiers.push([namespace.trim(), value.trim()]);
  };
  for (const [namespace, value] of Object.entries(entity.external_ids)) add(namespace, value);
  for (const identifier of entity.identity_identifiers ?? []) add(identifier.namespace, identifier.value);
  return identifiers;
}

export function matchExplanation(entity: IntelligenceEntity | Entity): string | null {
  if (!("match" in entity) || !entity.match) return null;
  if (entity.match.match_type === "relationship")
    return t("关联命中：{value} · {relationship}", {
      value: entity.match.matched_value ?? t("已发布对象"),
      relationship: entity.match.predicate ? relationshipLabel(entity.match.predicate) : t("已验证关系"),
    });
  const relation =
    entity.match.match_relation === "exact"
      ? t("精确匹配")
      : entity.match.match_relation === "partial"
        ? t("相关匹配")
        : t("语义相关");
  const sources = {
    canonical_name: "名称",
    alias: "别名",
    external_id: "外部标识",
    description: "描述",
    semantic: "语义关联",
    relationship: "已验证关联",
  } as const;
  const source = t(sources[entity.match.match_type]);
  const namespace = entity.match.namespace ? `${entity.match.namespace} · ` : "";
  const value = entity.match.matched_value
    ? t("：{value}", { value: `${namespace}${entity.match.matched_value}` })
    : "";
  return t("{source}{relation}{value}", { source, relation, value });
}

/** A compact row retains its complete match context and source description. */
export function entityResultContext(entity: IntelligenceEntity | Entity): string | null {
  const values = [matchExplanation(entity), entity.description].filter((value): value is string => Boolean(value));
  return values.length ? values.join(" · ") : null;
}
