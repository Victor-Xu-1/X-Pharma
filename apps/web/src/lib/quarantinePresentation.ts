import type { QuarantineStatus } from "./generated";

const labels: Record<QuarantineStatus, string> = {
  not_applicable: "未隔离",
  pending_review: "待审核",
  held: "留置待审",
  rescan_requested: "等待复扫",
  rejected: "永久拒绝",
  cleared: "已解除隔离",
};

/** Display vocabulary only; server decisions and action availability have existing owners. */
export function quarantineStatusLabel(status: QuarantineStatus): string {
  return labels[status];
}
