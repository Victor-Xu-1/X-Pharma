import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { regulatoryText as t } from "../../lib/i18n/regulatory";

export type RegulatorySaveFeedback =
  | { kind: "outcome"; outcome: SavedSearchCreationOutcome }
  | { kind: "error"; reason: string | null };

export function regulatorySaveFeedback(feedback: RegulatorySaveFeedback | null): string {
  if (!feedback) return "";
  if (feedback.kind === "error") return feedback.reason ?? t("监管检索保存失败");
  const { outcome } = feedback;
  if (outcome.kind === "monitor_failed")
    return t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
  return outcome.monitoring ? t("监管检索已保存并启用监控") : t("监管检索已保存");
}
