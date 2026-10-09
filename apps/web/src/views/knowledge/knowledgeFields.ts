import { formattingLocale } from "../../lib/i18n";
import { type knowledgeFieldMessages, knowledgeFieldText as text } from "../../lib/i18n/knowledgeFields";
import { recordValue } from "./knowledgeReading";
import { knowledgeTrialFieldText } from "./knowledgeTrialFields";

const labels: Record<string, keyof typeof knowledgeFieldMessages> = {
  name: "名称",
  registry_id: "登记编号",
  registry_name: "登记来源",
  overall_status: "试验状态",
  phases: "登记分期",
  enrollment: "登记参与人数",
  enrollment_type: "参与人数口径",
  conditions: "登记研究条件",
  start_date: "开始日期",
  completion_date: "完成日期",
  results_first_posted: "首次结果发布日期",
  official_title: "完整登记标题",
  acronym: "简称",
  study_type: "研究类型",
  sponsors: "登记申办方",
  interventions: "研究干预",
  outcomes: "研究终点",
  locations: "研究地点",
  arms: "试验分组",
  eligibility: "入组条件",
  study_design: "研究设计",
  result_disclosures: "结果披露",
  status_history: "状态历史",
  last_update_posted: "登记更新日期",
  result_evaluation: "结果评价记录",
  start_date_precision: "开始日期精度",
  completion_date_precision: "完成日期精度",
  citation: "记录定位",
  entity_roles: "关联角色",
  linked_entities: "关联实体",
  initiation_type: "启动类型",
};
const trialPrimary = [
  "registry_id",
  "overall_status",
  "phases",
  "enrollment",
  "enrollment_type",
  "conditions",
  "start_date",
  "start_date_precision",
  "completion_date",
  "completion_date_precision",
  "results_first_posted",
];

export type KnowledgeField = { key: string; label: string; value: string };

function fieldText(value: unknown, key: string): string {
  if (value === null || value === undefined) return text("未提供");
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) {
    if (!value.length) return text("0 项");
    const names = value.map((item) => {
      if (item === null || typeof item !== "object") return String(item);
      const record = recordValue(item);
      const name =
        record?.name ??
        record?.condition_name ??
        record?.intervention_name ??
        record?.organization_name ??
        record?.title;
      return typeof name === "string" ? name : null;
    });
    return names.every((name) => name !== null)
      ? names.join(formattingLocale() === "en-US" ? ", " : "、")
      : text("{count} 项（完整内容见原文）", { count: new Intl.NumberFormat(formattingLocale()).format(value.length) });
  }
  const record = recordValue(value);
  if (key === "citation") return typeof record?.locator === "string" ? record.locator : text("定位见完整原文");
  if (typeof record?.name === "string") return record.name;
  const fields = Object.entries(record ?? {});
  if (fields.every(([, field]) => field === null || typeof field !== "object")) {
    return (
      fields.map(([field, detail]) => `${field}: ${detail === null ? "null" : String(detail)}`).join(" · ") ||
      text("空记录")
    );
  }
  return text("{count} 个字段（完整内容见原文）", {
    count: new Intl.NumberFormat(formattingLocale()).format(fields.length),
  });
}

/** All supplied top-level fields remain reachable; never infer scientific status or units. */
export function knowledgeFields(value: unknown): { primary: KnowledgeField[]; remaining: KnowledgeField[] } | null {
  const record = recordValue(value);
  if (!record || record.fact_kind === "entity_alias" || !Object.keys(record).length) return null;
  if (Object.keys(record).length === 1 && "value" in record) return null;
  const entries = Object.entries(record).filter(([key]) => key !== "fact_kind");
  const primaryKeys = record.fact_kind === "trial" ? trialPrimary : entries.slice(0, 6).map(([key]) => key);
  const fields = entries.map(([key, field]) => ({
    key,
    label: Object.hasOwn(labels, key) ? text(labels[key]) : key,
    value: (record.fact_kind === "trial" ? knowledgeTrialFieldText(field, key, record) : null) ?? fieldText(field, key),
  }));
  return {
    primary: primaryKeys.flatMap((key) => fields.filter((field) => field.key === key)),
    remaining: fields.filter((field) => !primaryKeys.includes(field.key)),
  };
}
