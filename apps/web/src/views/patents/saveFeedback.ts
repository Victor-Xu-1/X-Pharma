import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { patentText as t } from "../../lib/i18n/patents";

export type PatentSaveFeedback =
  | { kind: "outcome"; outcome: SavedSearchCreationOutcome }
  | { kind: "error"; reason: string | null }
  | { kind: "comparison"; message: string };

export function patentSaveFeedback(feedback: PatentSaveFeedback | null): string {
  if (!feedback) return "";
  if (feedback.kind === "comparison") return feedback.message;
  if (feedback.kind === "error") return feedback.reason ?? t("专利检索保存失败");
  const { outcome } = feedback;
  if (outcome.kind === "monitor_failed")
    return t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
  return outcome.monitoring ? t("专利检索已保存并启用监控") : t("专利检索已保存");
}
