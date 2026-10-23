import type { SavedSearchCreationOutcome } from "../../lib/contracts/savedSearchCreation";
import { newsText as t } from "../../lib/i18n/news";

export type NewsSaveFeedback =
  | { kind: "outcome"; outcome: SavedSearchCreationOutcome }
  | { kind: "error"; reason: string | null };

export function newsSaveFeedback(feedback: NewsSaveFeedback | null): string {
  if (!feedback) return "";
  if (feedback.kind === "error") return feedback.reason ?? t("新闻与会议检索保存失败");
  const { outcome } = feedback;
  if (outcome.kind === "monitor_failed")
    return t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
  return outcome.monitoring ? t("新闻与会议检索已保存并启用监控") : t("新闻与会议检索已保存");
}
