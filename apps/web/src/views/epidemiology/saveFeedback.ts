import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
export type EpidemiologySaveFeedback =
  | { kind: "outcome"; outcome: SavedSearchCreationOutcome }
  | { kind: "error"; reason: string | null };
export function epidemiologySaveFeedback(feedback: EpidemiologySaveFeedback | null): string {
  if (!feedback) return "";
  if (feedback.kind === "error") return feedback.reason ?? t("流行病学检索保存失败");
  const outcome = feedback.outcome;
  if (outcome.kind === "monitor_failed")
    return t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
  return outcome.monitoring ? t("流行病学检索已保存并启用监控") : t("流行病学检索已保存");
}
