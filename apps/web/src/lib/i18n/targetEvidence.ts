import type { TargetEvidence } from "../contracts/target";
import { createTranslator } from "./translator";

export const targetEvidenceMessages = {
  暂无关联实体: "No related entities",
  靶点实体关系: "Target entity relationships",
  方向: "Direction",
  关系: "Relationship",
  关联实体: "Related entity",
  类型: "Type",
  指向: "To",
  来自: "From",
  "暂无遗传、表达或转化证据": "No genetic, expression or translational evidence",
  "当前可用来源和更新时间范围内未观察到记录，不代表该靶点不存在相关证据":
    "No records were observed within the available sources and update range; this does not mean evidence for this target does not exist.",
  转化证据筛选: "Translational evidence filters",
  证据类型: "Evidence type",
  证据方向: "Evidence direction",
  全部: "All",
  遗传关联: "Genetic association",
  表达: "Expression",
  功能验证: "Functional validation",
  转化研究: "Translational research",
  生物标志物: "Biomarker",
  安全性: "Safety",
  支持: "Supports",
  反对: "Opposes",
  中性: "Neutral",
  未知: "Unknown",
  支持靶点假设: "Supports the target hypothesis",
  反对靶点假设: "Opposes the target hypothesis",
  支持疾病机制: "Supports the disease mechanism",
  反对疾病机制: "Opposes the disease mechanism",
  方向未知: "Direction unknown",
  "{shown} / {total} 条": "{shown} / {total} records",
  当前筛选条件下无匹配证据: "No evidence matches the current filters",
  靶点转化证据: "Target translational evidence",
  "类型 / 方向": "Type / direction",
  疾病: "Disease",
  研究与人群: "Study and population",
  "组织 / 变异": "Tissue / variant",
  效应: "Effect",
  证据摘要: "Evidence summary",
  观察时间: "Observation date",
  原始证据: "Original evidence",
  人群未记录: "Population not recorded",
  变异未记录: "Variant not recorded",
} as const;

export const targetEvidenceText = createTranslator(targetEvidenceMessages);
export const targetEvidenceTypeKeys = {
  genetic_association: "遗传关联",
  expression: "表达",
  functional: "功能验证",
  translational: "转化研究",
  biomarker: "生物标志物",
  safety: "安全性",
} as const satisfies Record<TargetEvidence["evidence_type"], keyof typeof targetEvidenceMessages>;
export const targetEvidenceDirectionKeys = {
  supports: { option: "支持", statement: "支持靶点假设" },
  opposes: { option: "反对", statement: "反对靶点假设" },
  neutral: { option: "中性", statement: "中性" },
  unknown: { option: "未知", statement: "方向未知" },
} as const satisfies Record<
  TargetEvidence["direction"],
  Record<"option" | "statement", keyof typeof targetEvidenceMessages>
>;

export function targetEvidenceTypeLabel(value: TargetEvidence["evidence_type"]): string {
  return Object.hasOwn(targetEvidenceTypeKeys, value) ? targetEvidenceText(targetEvidenceTypeKeys[value]) : value;
}
export function targetEvidenceDirectionLabel(
  value: TargetEvidence["direction"],
  subject: "target" | "disease" = "target",
): string {
  if (subject === "disease" && value === "supports") return targetEvidenceText("支持疾病机制");
  if (subject === "disease" && value === "opposes") return targetEvidenceText("反对疾病机制");
  return Object.hasOwn(targetEvidenceDirectionKeys, value)
    ? targetEvidenceText(targetEvidenceDirectionKeys[value].statement)
    : value;
}
