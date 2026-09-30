export const dealTypeLabels: Record<string, string> = {
  license: "许可",
  collaboration: "合作",
  acquisition: "收购",
  merger: "合并",
  option: "选择权",
  co_development: "共同开发",
  commercialization: "商业化",
};

export const statusLabels: Record<string, string> = {
  announced: "已披露",
  active: "进行中",
  completed: "已完成",
  terminated: "已终止",
  withdrawn: "已撤回",
  superseded: "已替代",
  unknown: "未披露",
};

export const directionLabels: Record<string, string> = {
  domestic: "境内",
  inbound: "引进",
  outbound: "对外许可",
  cross_border: "跨境",
  global: "全球",
  undisclosed: "未披露",
};

export const partyRoleLabels: Record<string, string> = {
  licensor: "许可方",
  licensee: "被许可方",
  seller: "转让方",
  buyer: "受让方",
  acquirer: "收购方",
  target: "被收购方",
  partner: "合作方",
  investor: "投资方",
  investee: "被投方",
  other: "角色未披露",
};

export const rightTypeLabels: Record<string, string> = {
  research: "研究",
  development: "开发",
  manufacturing: "生产",
  commercialization: "商业化",
  co_development: "共同开发",
  co_promotion: "共同推广",
  distribution: "分销",
  option: "选择权",
  other: "其他",
};

export const phaseLabels: Record<string, string> = {
  discovery: "发现",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I期",
  phase_1_2: "I/II期",
  phase_2: "II期",
  phase_2_3: "II/III期",
  phase_3: "III期",
  filed: "已申报",
  approved: "已批准",
  discontinued: "已终止",
};

export function formatAmount(value: number | null, currency: string | null) {
  if (value === null) return "未披露";
  const prefix = currency ? `${currency} ` : "";
  if (value >= 1_000_000_000) return `${prefix}${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `${prefix}${(value / 1_000_000).toFixed(1)}M`;
  return `${prefix}${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value)}`;
}

export function displayTerms(terms: Record<string, unknown>) {
  const entries = Object.entries(terms);
  if (!entries.length) return "--";
  return entries
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" · ");
}
