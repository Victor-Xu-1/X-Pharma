import type { TrialResultEvaluation } from "./generated";

export const trialInitiationTypeLabels: Record<string, string> = {
  iit: "IIT（研究者发起）",
  ist: "IST（申办方发起）",
};

export const trialTherapyLineLabels: Record<string, string> = {
  first_line: "一线治疗",
  second_line: "二线治疗",
  third_or_later: "三线及以后",
  prevention: "预防",
  treatment_naive: "初治",
  add_on: "加用治疗",
  adjuvant: "辅助治疗",
  neoadjuvant: "新辅助治疗",
  maintenance: "维持治疗",
  consolidation: "巩固治疗",
  induction: "诱导治疗",
  conversion: "转化治疗",
};

export const trialResultEvaluationLabels: Record<TrialResultEvaluation, string> = {
  unfavorable: "不佳",
  not_superior: "非优",
  non_inferior: "非劣",
  similar: "相似",
  positive: "积极",
  superior: "优效",
  terminated: "终止",
};

export const trialKeyResultLabels: Record<"true" | "false", string> = {
  true: "有关键结果",
  false: "无关键结果",
};

export function validateTrialResultFilters(values: { hasResults: string; resultEvaluation: string }): string | null {
  if (values.hasResults === "false" && values.resultEvaluation) {
    return "选择“未发布结果”时不能同时限定结果评价";
  }
  return null;
}
