import type { QuarantineAction } from "./contracts/dataFactory";
import { quarantineText as t } from "./i18n/factoryQuarantine";

const labels = {
  not_applicable: "未隔离",
  pending_review: "待审核",
  held: "留置待审",
  rescan_requested: "等待复扫",
  rejected: "永久拒绝",
  cleared: "已解除隔离",
} as const;

/** Display vocabulary only; server decisions and action availability have existing owners. */
export function quarantineStatusLabel(status: string): string {
  return Object.hasOwn(labels, status) ? t(labels[status as keyof typeof labels]) : status;
}

const actionLabels = { hold: "留置待审", reject: "永久拒绝", rescan: "重新安全扫描" } as const;
const decisionLabels = {
  scan_detected: "扫描发现威胁",
  hold: "留置待审",
  reject: "永久拒绝",
  rescan: "申请重新扫描",
  scan_clean: "复扫结果清洁",
  rescan_failed: "复扫启动失败",
} as const;
export function quarantineActionLabel(action: string): string {
  return Object.hasOwn(actionLabels, action) ? t(actionLabels[action as keyof typeof actionLabels]) : action;
}
export function quarantineDecisionLabel(action: string): string {
  return Object.hasOwn(decisionLabels, action) ? t(decisionLabels[action as keyof typeof decisionLabels]) : action;
}
const pendingActions: readonly QuarantineAction[] = ["hold", "reject", "rescan"];
const heldActions: readonly QuarantineAction[] = ["reject", "rescan"];
const noActions: readonly QuarantineAction[] = [];
export function quarantineActions(status: string): readonly QuarantineAction[] {
  return status === "pending_review" ? pendingActions : status === "held" ? heldActions : noActions;
}
