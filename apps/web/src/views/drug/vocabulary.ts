export { eventTypeLabels as regulatoryEventLabels, regulatoryStatusLabels } from "../../lib/regulatoryDisplay";
export {
  trialInitiationTypeLabels as trialInitiationLabels,
  trialResultEvaluationLabels as trialResultLabels,
} from "../../lib/trialFilters";
export { disclosureTypeLabels, trialRoleLabels } from "../trials/vocabulary";
export const approvalEventTypes = new Set(["approval", "conditional_approval"]);

export const jurisdictionLabels: Record<string, string> = {
  CN: "中国",
  EU: "欧洲",
  Global: "全球",
  JP: "日本",
  US: "美国",
};

export const lineOfTherapyLabels: Record<string, string> = {
  adjuvant: "辅助治疗",
  first_line: "一线",
  maintenance: "维持治疗",
  neoadjuvant: "新辅助治疗",
  second_line: "二线",
  third_line: "三线",
  third_line_or_later: "三线及以上",
  third_or_later: "三线及以上",
};

export const routeLabels: Record<string, string> = {
  inhaled: "吸入",
  intramuscular: "肌内注射",
  intravenous: "静脉给药",
  oral: "口服",
  subcutaneous: "皮下注射",
  topical: "局部用药",
};

export const dosageFormLabels: Record<string, string> = {
  capsule: "胶囊",
  injection: "注射剂",
  solution: "溶液剂",
  tablet: "片剂",
};

export const programStatusLabels: Record<string, string> = {
  active: "在研",
  inactive: "非活跃",
  unknown: "状态未知",
};

export const organizationRoleLabels: Record<string, string> = {
  originator: "原研",
  collaborator: "合作研发",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

export const geographyLabels: Record<string, string> = {
  CN: "中国",
  China: "中国",
  china: "中国",
  EU: "欧洲",
  Europe: "欧洲",
  europe: "欧洲",
  Global: "全球",
  global: "全球",
  "Greater China": "大中华区",
  JP: "日本",
  Japan: "日本",
  japan: "日本",
  US: "美国",
  us: "美国",
};

export const innovationTypeLabels: Record<string, string> = {
  best_in_class: "Best-in-Class",
  first_in_class: "First-in-Class",
  me_better: "Me-better",
  me_too: "Me-too",
};

export const drugCategoryLabels: Record<string, string> = {
  biologic: "生物制品",
  chemical_drug: "化学药",
  gene_therapy: "基因治疗",
  traditional_medicine: "中药",
};
