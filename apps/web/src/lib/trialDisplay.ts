const clinicalTrialPhaseLabels: Record<string, string> = {
  EARLY_PHASE1: "早期 I 期",
  PHASE1: "I 期",
  PHASE1_PHASE2: "I/II 期",
  PHASE2: "II 期",
  PHASE2_PHASE3: "II/III 期",
  PHASE3: "III 期",
  PHASE4: "IV 期",
  NA: "不适用",
};

const clinicalTrialStatusLabels: Record<string, string> = {
  NOT_YET_RECRUITING: "尚未招募",
  RECRUITING: "招募中",
  ENROLLING_BY_INVITATION: "邀请入组",
  ACTIVE_NOT_RECRUITING: "进行中，停止招募",
  SUSPENDED: "暂停",
  TERMINATED: "终止",
  COMPLETED: "已完成",
  WITHDRAWN: "撤回",
  UNKNOWN: "未知",
};

const clinicalTrialStudyTypeLabels: Record<string, string> = {
  INTERVENTIONAL: "干预性研究",
  OBSERVATIONAL: "观察性研究",
  EXPANDED_ACCESS: "扩大使用",
};

function vocabularyKey(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, "_");
}

function readableFallback(value: string, emptyLabel: string): string {
  const normalized = value.trim();
  return normalized ? normalized.replaceAll("_", " ") : emptyLabel;
}

export function clinicalTrialPhaseLabel(value: string): string {
  return clinicalTrialPhaseLabels[vocabularyKey(value)] ?? readableFallback(value, "阶段未记录");
}

export function clinicalTrialStatusLabel(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";
  return clinicalTrialStatusLabels[vocabularyKey(normalized)] ?? readableFallback(normalized, "未知");
}

export function clinicalTrialStudyTypeLabel(value: string | null | undefined): string {
  const normalized = value?.trim() ?? "";
  return clinicalTrialStudyTypeLabels[vocabularyKey(normalized)] ?? readableFallback(normalized, "未记录");
}
