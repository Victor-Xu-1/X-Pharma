import type { PipelineSaveOutcome } from "../../lib/contracts/pipeline";
import { pipelineText } from "../../lib/i18n/pipeline";

export type PipelineFeedback = PipelineSaveOutcome | { kind: "failed"; reason: string | null } | string;

export function pipelineSaveFeedback(outcome: PipelineFeedback): string {
  if (typeof outcome === "string") return outcome;
  if (outcome.kind === "failed") return outcome.reason ?? pipelineText("管线检索保存失败");
  return outcome.kind === "saved"
    ? pipelineText(outcome.monitoring ? "管线检索已保存并启用监控" : "管线检索已保存")
    : pipelineText("检索已保存，但监控未启用：{reason}", {
        reason: outcome.reason ?? pipelineText("未知错误"),
      });
}
