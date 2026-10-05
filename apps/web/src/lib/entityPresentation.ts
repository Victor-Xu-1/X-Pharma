import type { IntelligenceEntity } from "./contracts/intelligence";
import { isPublicEntityIdentifierNamespace } from "./publicEntity";
import type { Entity } from "./types";

export const entityLabels: Record<string, string> = {
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
};

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
    return `关联命中：${entity.match.matched_value ?? "已发布对象"} · ${entity.match.predicate ?? "已验证关系"}`;
  const relation =
    entity.match.match_relation === "exact"
      ? "精确匹配"
      : entity.match.match_relation === "partial"
        ? "相关匹配"
        : "语义相关";
  const source = {
    canonical_name: "名称",
    alias: "别名",
    external_id: "外部标识",
    description: "描述",
    semantic: "语义关联",
    relationship: "已验证关联",
  }[entity.match.match_type];
  const namespace = entity.match.namespace ? `${entity.match.namespace} · ` : "";
  const value = entity.match.matched_value ? `：${namespace}${entity.match.matched_value}` : "";
  return `${source}${relation}${value}`;
}
