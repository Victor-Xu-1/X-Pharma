import { getLocale } from "./locale";
import { professionalQueryLabel } from "./professionalQuery";
import { createTranslator } from "./translator";

export const professionalValidationMessages = {
  "{label}起始值不能晚于结束值": "{label}: the start must not be later than the end",
  "{label}起始日期不能晚于结束日期": "{label}: the start date must not be later than the end date",
  "{label}下限不能高于上限": "{label}: the minimum must not exceed the maximum",
  "{label}必须是有效的日历日期": "{label}: enter a valid calendar date",
  "{label}必须是有限的非负十进制金额": "{label}: enter a finite, non-negative decimal amount",
  "{label}包含不支持的筛选值": "{label}: this filter value is not supported",
  "选择“无临床结果”时不能同时限定结果评价":
    "Result evaluation cannot be restricted when No clinical results is selected",
  "选择“无交易记录”时不能同时限定交易金额或币种":
    "Deal amount or currency cannot be restricted when No deal records is selected",
  按交易金额查询时必须选择币种: "Choose a currency to search by deal amount",
  按交易金额排序时必须选择币种: "Choose a currency to sort by deal amount",
  币种必须是三位大写字母代码: "Use a three-letter uppercase currency code",
  交易潜在总额下限不能大于上限: "The minimum total potential deal amount must not exceed the maximum",
  "选择“未发布结果”时不能同时限定结果评价":
    "Result evaluation cannot be restricted when Results not posted is selected",
  引进或对外许可必须选择方向参照地区: "Choose a direction reference jurisdiction for inbound or outbound licensing",
} as const;
const validationText = createTranslator(professionalValidationMessages);
type ValidationKey = keyof typeof professionalValidationMessages;

// Exact application-owned validator messages only. This is presentation, not a
// second validation rule or a parser for researcher/provider text.
const messages = new Map<string, { key: ValidationKey; label?: string }>();
for (const label of [
  "状态日期",
  "全球阶段开始日期",
  "中国阶段开始日期",
  "里程碑日期",
  "结果发布日期",
  "结果披露日期",
  "优先权日期",
  "到期日期",
  "统计周期",
  "发布日期",
  "监管决定日期",
  "来源更新日期",
]) {
  messages.set(`${label}起始值不能晚于结束值`, { key: "{label}起始值不能晚于结束值", label });
}
for (const label of ["初始披露日期", "终止日期", "信息更新日期"]) {
  messages.set(`${label}起始日期不能晚于结束日期`, { key: "{label}起始日期不能晚于结束日期", label });
  messages.set(`${label}必须是有效的日历日期`, { key: "{label}必须是有效的日历日期", label });
}
for (const label of ["首付款", "潜在总额"]) {
  messages.set(`${label}下限不能高于上限`, { key: "{label}下限不能高于上限", label });
  messages.set(`${label}必须是有限的非负十进制金额`, { key: "{label}必须是有限的非负十进制金额", label });
}
for (const label of ["交易状态", "交易方向", "参与角色", "权益类型", "交易时阶段", "当前最高阶段"]) {
  messages.set(`${label}包含不支持的筛选值`, { key: "{label}包含不支持的筛选值", label });
}
for (const key of Object.keys(professionalValidationMessages) as ValidationKey[]) {
  if (!key.includes("{label}")) messages.set(key, { key });
}

export function professionalValidationText(message: string): string {
  const known = messages.get(message);
  if (!known || getLocale() === "zh-CN") return message;
  return validationText(known.key, known.label ? { label: professionalQueryLabel(known.label) } : {});
}
