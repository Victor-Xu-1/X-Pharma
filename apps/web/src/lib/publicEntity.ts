import type { Entity } from "./types";

/** Only business-facing entity attributes may be rendered by human research pages. */
export const publicEntityAttributeLabels: Record<string, string> = {
  biomarker: "生物标志物",
  cas_number: "CAS 号",
  chemical_name: "化学名称",
  country: "国家/地区",
  drug_category: "药品类别",
  development_phase: "研发阶段",
  disease_area: "疾病领域",
  english_name: "英文名称",
  headquarters: "总部所在地",
  innovation_type: "创新类型",
  inchi: "InChI",
  inchi_key: "InChI Key",
  mechanism: "作用机制",
  modality: "药物模态",
  organism: "物种",
  program_tag: "项目标签",
  program_tags: "项目标签",
  region: "地区",
  smiles: "结构表达式",
  status_detail: "进展说明",
  target_class: "靶点类别",
  therapeutic_area: "治疗领域",
};

const hiddenIdentifierNamespacePrefixes = ["pharmcube", "internal", "source", "ingestion"];

export function isPublicEntityIdentifierNamespace(namespace: string): boolean {
  const normalized = namespace.trim().toLocaleLowerCase().replaceAll("-", "_");
  return (
    Boolean(normalized) &&
    !hiddenIdentifierNamespacePrefixes.some((prefix) => normalized === prefix || normalized.startsWith(`${prefix}_`))
  );
}

function isPublicAttributeValue(value: unknown): boolean {
  if (value === null || ["string", "number", "boolean"].includes(typeof value)) return true;
  return (
    Array.isArray(value) &&
    value.every((item) => item === null || ["string", "number", "boolean"].includes(typeof item))
  );
}

export function publicEntityAttributes(entity: Pick<Entity, "attributes">): Array<[string, unknown]> {
  return Object.entries(entity.attributes).filter(
    ([key, value]) => key in publicEntityAttributeLabels && isPublicAttributeValue(value),
  );
}
