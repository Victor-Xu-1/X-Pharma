import type { PipelineLandscapeBucketRead } from "../../lib/generated";
import { localizedDevelopmentPhase, localizedProgramModality } from "../../lib/i18n/programVocabulary";
import { phaseDisplayOrder, spacedPhaseLabels as phaseLabels } from "../../lib/phasePresentation";
export function labeledPhases(buckets: PipelineLandscapeBucketRead[]) {
  return buckets.map((bucket) => ({
    ...bucket,
    label: Object.hasOwn(phaseLabels, bucket.key) ? localizedDevelopmentPhase(bucket.key, true) : bucket.label,
  }));
}

export function labeledModalities(buckets: PipelineLandscapeBucketRead[]) {
  return buckets.map((bucket) => ({ ...bucket, label: localizedProgramModality(bucket.label || bucket.key) }));
}

export function phaseComposition(bucket: PipelineLandscapeBucketRead) {
  return Object.entries(bucket.phase_counts ?? {})
    .sort(([left], [right]) => phaseDisplayOrder.indexOf(left) - phaseDisplayOrder.indexOf(right))
    .map(([phase, count]) => `${localizedDevelopmentPhase(phase, true)} ${count}`)
    .join(" · ");
}
