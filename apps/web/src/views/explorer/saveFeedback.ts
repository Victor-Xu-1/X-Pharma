import type { EntitySearchSaveOutcome } from "../../lib/contracts/intelligence";
import { createTranslator } from "../../lib/i18n";
import { explorerMessages } from "../../lib/i18n/explorer";

export type ExplorerFeedback = EntitySearchSaveOutcome | { kind: "failed"; reason: string | null } | string;
const t = createTranslator(explorerMessages);

/** Retain outcome identity; translate product copy at render time, never a source reason. */
export function explorerSaveFeedback(outcome: ExplorerFeedback): string {
  if (typeof outcome === "string") return outcome;
  if (outcome.kind === "failed") return outcome.reason ?? t("保存失败");
  return outcome.kind === "saved"
    ? t(outcome.monitoring ? "基础查询检索已保存并启用监控" : "基础查询检索已保存")
    : t("检索已保存，但监控未启用：{reason}", { reason: outcome.reason ?? t("未知错误") });
}
