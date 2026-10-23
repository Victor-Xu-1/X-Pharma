import { createTranslator } from "./translator";

// Fixed first-party warning in pipeline_search/entity_dossier; never a source narrative.
const coverageWarning = "暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。";
const warningText = createTranslator({
  [coverageWarning]:
    "Missing records do not imply that none exist globally. Results depend on source access, update time and visibility.",
} as const);

/** Translate only a verified application message; arbitrary/source warnings remain verbatim. */
export function intelligenceWarningText(value: string): string {
  return value === coverageWarning ? warningText(coverageWarning) : value;
}
