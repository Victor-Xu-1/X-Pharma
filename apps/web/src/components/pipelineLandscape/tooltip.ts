import type { PipelineLandscapeBucketRead } from "../../lib/generated";
import type { Locale } from "../../lib/i18n";
import { pipelineLandscapeText } from "../../lib/i18n/pipelineLandscape";
import { localizedDevelopmentPhase } from "../../lib/i18n/programVocabulary";

function escapeHtml(value: string): string {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return value.replace(/[&<>"']/g, (character) => entities[character]);
}

/** ECharts owns markup; source names and unknown phase captions never own HTML. */
export function landscapeTooltip(bucket: PipelineLandscapeBucketRead, locale: Locale, unitLabel?: string): string {
  const phases = Object.entries(bucket.phase_counts ?? {})
    .filter(([, count]) => count > 0)
    .map(([phase, count]) => `${escapeHtml(localizedDevelopmentPhase(phase, true))}: ${count}`)
    .join("<br/>");
  const count =
    unitLabel === undefined
      ? pipelineLandscapeText("{count} 个项目", { count: bucket.count }, locale)
      : pipelineLandscapeText("{count} {unit}", { count: bucket.count, unit: escapeHtml(unitLabel) }, locale);
  return `${escapeHtml(bucket.label)}<br/>${count} · ${(bucket.share * 100).toFixed(1)}%${phases ? `<br/>${phases}` : ""}`;
}
