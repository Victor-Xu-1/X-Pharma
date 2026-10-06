import type { StagedFactRead } from "./generated";

const labels: Record<string, string> = {
  claim: "研究结论",
  program: "研发管线",
  trial: "临床试验",
  structure: "化合物结构",
  activity: "实验活性",
  target_profile: "靶点资料",
  target_evidence: "靶点证据",
  patent: "专利",
  deal: "交易",
  regulatory: "监管事件",
  epidemiology: "流行病学",
  news: "行业动态",
  phase: "研发阶段",
  global_phase: "全球阶段",
  china_phase: "中国阶段",
  status: "状态",
  canonical_smiles: "规范 SMILES",
  standard_inchi: "标准 InChI",
  standard_inchi_key: "标准 InChIKey",
  molecular_formula: "分子式",
  modality: "药物类型",
  mechanism_of_action: "作用机制",
  name: "名称",
  entity_type: "对象类型",
  drug: "药物",
  subject: "研究对象",
  targets: "靶点",
  value: "数值",
  reported_value: "报告值",
  reported_type: "测量指标",
  reported_units: "报告单位",
  reported_relation: "数值关系",
  standard_value: "标准值",
  standard_units: "标准单位",
  assay_name: "实验",
  assay_type: "实验类型",
  source_updated_at: "来源更新时间",
};

export function governanceLabel(value: string): string {
  return value
    .split(".")
    .map((part) => labels[part] ?? part)
    .join(" / ");
}

type Difference = { path: string; before: unknown; after: unknown };
const absent = Symbol("absent");

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function payloadDifferences(before: unknown, after: unknown, path = ""): Difference[] {
  if (object(before) && object(after)) {
    return [...new Set([...Object.keys(before), ...Object.keys(after)])].sort().flatMap((key) => {
      if (key === "citation") return [];
      return payloadDifferences(
        Object.hasOwn(before, key) ? before[key] : absent,
        Object.hasOwn(after, key) ? after[key] : absent,
        path ? `${path}.${key}` : key,
      );
    });
  }
  return JSON.stringify(before) === JSON.stringify(after) && before !== absent && after !== absent
    ? []
    : [{ path, before, after }];
}

export function reviewValue(value: unknown): string {
  if (value === absent) return "字段不存在";
  if (value === null) return "未披露";
  return typeof value === "string" ? value : (JSON.stringify(value) ?? "未披露");
}

export function groupReviewFacts(facts: StagedFactRead[]): StagedFactRead[][] {
  const groups = new Map<string, StagedFactRead[]>();
  for (const fact of facts) {
    const key = fact.fact_key ?? fact.id;
    const group = groups.get(key) ?? [];
    group.push(fact);
    groups.set(key, group);
  }
  return [...groups.values()];
}
