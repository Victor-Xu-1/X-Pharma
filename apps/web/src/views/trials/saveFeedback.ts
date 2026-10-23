import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { clinicalText as t } from "../../lib/i18n/clinical";
export type ClinicalFeedback = SavedSearchCreationOutcome | { kind: "failed"; reason: string | null } | string;
export function clinicalSaveFeedback(outcome: ClinicalFeedback): string {
  if (typeof outcome === "string") return outcome;
  if (outcome.kind === "failed") return outcome.reason ?? t("临床试验检索保存失败");
  return outcome.kind === "saved"
    ? t(outcome.monitoring ? "临床试验检索已保存并启用监控" : "临床试验检索已保存")
    : t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
}
