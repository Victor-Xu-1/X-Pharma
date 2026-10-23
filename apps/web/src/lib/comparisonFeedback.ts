import type { MessageParameters } from "./i18n";
import { type comparisonMessages, comparisonText } from "./i18n/comparison";

type ComparisonMessageKey = keyof typeof comparisonMessages;
export type ComparisonFeedback =
  | { key: ComparisonMessageKey; parameters?: MessageParameters }
  | { raw: string }
  | { created: ComparisonFeedback };

export function comparisonFeedbackText(feedback: ComparisonFeedback | null): string {
  if (!feedback) return "";
  if ("raw" in feedback) return feedback.raw;
  if ("created" in feedback) {
    return comparisonText("列表已创建，但成员尚未加入；已保留新列表，请重新确认加入。{reason}", {
      reason: comparisonFeedbackText(feedback.created),
    });
  }
  return comparisonText(feedback.key, feedback.parameters);
}

/** Normalize known write conflicts; preserve an unknown server reason verbatim. */
export function comparisonFailure(caught: unknown, fallback: ComparisonMessageKey): ComparisonFeedback {
  if (!(caught instanceof Error)) return { key: fallback };
  if (/already in this comparison set/i.test(caught.message)) {
    return { key: "列表内容刚刚发生变化，请重新确认后再试" };
  }
  if (/limited to \d+ entities/i.test(caught.message)) return { key: "该对比列表已达到 20 个实体上限" };
  if (/version|expected_version|changed concurrently/i.test(caught.message)) {
    return { key: "列表内容已更新，请重新确认后再试" };
  }
  return /[\u3400-\u9fff]/u.test(caught.message) ? { raw: caught.message } : { key: fallback };
}
