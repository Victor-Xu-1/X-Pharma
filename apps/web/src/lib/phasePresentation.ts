import type { DevelopmentPhase } from "./generated";

const phaseNames: Record<DevelopmentPhase, { full: string; compact: string }> = {
  discovery: { full: "发现阶段", compact: "发现" },
  preclinical: { full: "临床前", compact: "临床前" },
  ind: { full: "IND", compact: "IND" },
  early_phase_1: { full: "早期 I 期临床", compact: "早期 I 期" },
  phase_1: { full: "I 期临床", compact: "I期" },
  phase_1_2: { full: "I/II 期临床", compact: "I/II期" },
  phase_2: { full: "II 期临床", compact: "II期" },
  phase_2_3: { full: "II/III 期临床", compact: "II/III期" },
  phase_3: { full: "III 期临床", compact: "III期" },
  filed: { full: "已申报", compact: "申报" },
  approved: { full: "已批准", compact: "已批准" },
  discontinued: { full: "已终止", compact: "终止" },
  unknown: { full: "阶段未知", compact: "阶段未知" },
};

export const developmentPhases: ReadonlySet<DevelopmentPhase> = new Set(Object.keys(phaseNames) as DevelopmentPhase[]);
export const compactPhaseLabels: Record<string, string> = Object.fromEntries(
  Object.entries(phaseNames).map(([phase, names]) => [phase, names.compact]),
);
compactPhaseLabels.__missing__ = "未披露";

export const fullPhaseLabels: Record<string, string> = Object.fromEntries(
  Object.entries(phaseNames).map(([phase, names]) => [phase, names.full]),
);
export const targetPhaseLabels: Record<string, string> = {
  ...Object.fromEntries(
    Object.entries(compactPhaseLabels).map(([phase, label]) => [phase, label.replace(/([IV])期/g, "$1 期")]),
  ),
  discovery: "药物发现",
  filed: "申报上市",
  discontinued: "已终止",
};
export const trialLinkedPhaseLabels: Record<string, string> = {
  ...fullPhaseLabels,
  ind: "申报临床",
  filed: "申请上市",
  approved: "批准上市",
  discontinued: "停止研发",
};

export function phaseLabel(value: string | null | undefined): string {
  if (!value) return "未披露";
  return phaseNames[value.toLowerCase() as DevelopmentPhase]?.full ?? value;
}

export const phaseDisplayOrder: readonly string[] = [
  "approved",
  "filed",
  "phase_3",
  "phase_2_3",
  "phase_2",
  "phase_1_2",
  "phase_1",
  "early_phase_1",
  "ind",
  "preclinical",
  "discovery",
  "discontinued",
  "unknown",
  "__missing__",
];
