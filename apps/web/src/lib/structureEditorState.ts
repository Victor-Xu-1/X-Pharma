export function isStructureApplyDisabled({
  ready,
  busy,
  hasStructure,
}: {
  ready: boolean;
  busy: boolean;
  hasStructure: boolean;
}) {
  return !ready || busy || !hasStructure;
}
