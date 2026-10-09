import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { dealText as t } from "../../lib/i18n/deals";

export type DealSaveFeedback =
  | { kind: "outcome"; outcome: SavedSearchCreationOutcome }
  | { kind: "error"; reason: string | null }
  | { kind: "comparison"; message: string };

export function dealSaveFeedback(feedback: DealSaveFeedback | null): string {
  if (!feedback) return "";
  if (feedback.kind === "comparison") return feedback.message;
  if (feedback.kind === "error") return feedback.reason ?? t("交易检索保存失败");
  if (feedback.outcome.kind === "monitor_failed")
    return t("检索已保存，但监控未启用：{reason}", { reason: feedback.outcome.reason ?? t("未知错误") });
  return feedback.outcome.monitoring ? t("交易检索已保存并启用监控") : t("交易检索已保存");
}
