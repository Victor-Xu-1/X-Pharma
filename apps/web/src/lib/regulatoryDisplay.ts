export const eventTypeLabels: Record<string, string> = {
  submission: "申报",
  acceptance: "受理",
  priority_review: "优先审评",
  approval: "批准",
  conditional_approval: "附条件批准",
  designation: "资格认定",
  label_update: "标签更新",
  safety_signal: "安全信号",
  safety_communication: "安全沟通",
  rejection: "拒绝",
  withdrawal: "撤回",
  suspension: "暂停",
  other: "其他",
};

export const regulatoryStatusLabels: Record<string, string> = {
  active: "有效",
  approved: "已批准",
  inactive: "失效",
  pending: "待处理",
  rejected: "未批准",
  suspended: "暂停",
  withdrawn: "已撤回",
};

export const designationLabels: Record<string, string> = {
  breakthrough_therapy: "突破性疗法",
  fast_track: "快速通道",
  priority_review: "优先审评",
  accelerated_approval: "加速批准",
  orphan_drug: "孤儿药",
  prime: "PRIME",
  sakigake: "先驱审查",
  conditional_marketing_authorisation: "附条件上市许可",
  other: "其他资格",
};

export const labelChangeLabels: Record<string, string> = {
  initial_label: "初始标签",
  indication_expansion: "适应症扩展",
  population_expansion: "人群扩展",
  restriction: "使用限制",
  dosing_update: "剂量更新",
  administration_update: "给药更新",
  safety_update: "安全性更新",
  boxed_warning: "黑框警告",
  contraindication: "禁忌更新",
  other: "其他标签变更",
};

export const safetySignalLabels: Record<string, string> = {
  adverse_event: "不良事件",
  boxed_warning: "黑框警告",
  contraindication: "禁忌",
  risk_management: "风险管理",
  recall: "召回",
  clinical_hold: "临床暂停",
  postmarketing_requirement: "上市后要求",
  other: "其他信号",
};

export const severityLabels: Record<string, string> = {
  informational: "提示",
  moderate: "中度",
  serious: "严重",
  severe: "重度",
  life_threatening: "危及生命",
  fatal: "致死",
  unknown: "未分级",
};

export const safetyStatusLabels: Record<string, string> = {
  detected: "已识别",
  under_evaluation: "评估中",
  confirmed: "已确认",
  monitoring: "持续监测",
  resolved: "已解决",
  withdrawn: "已撤回",
  unknown: "状态未披露",
};

export const boxedWarningLabels: Record<string, string> = {
  true: "有",
  false: "无",
};
