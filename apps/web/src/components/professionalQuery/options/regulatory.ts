import type { loadRegulatoryFacetCatalog } from "../../../lib/contracts/regulatory";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import {
  boxedWarningLabels,
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../../../lib/regulatoryDisplay";
import { type FacetCatalogState, facetOptions, labeledFacetOptions } from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function regulatoryOptions(
  draft: ProfessionalSearchDraft,
  regulatoryCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadRegulatoryFacetCatalog>>>,
) {
  const regulatoryCatalogState: FacetCatalogState = regulatoryCatalog.isPending
    ? "loading"
    : regulatoryCatalog.isError
      ? "failed"
      : "ready";
  const regulatoryAgencyOptions = facetOptions(regulatoryCatalog.data?.facets?.agency, [draft.regulatoryAgency]);
  const regulatoryJurisdictionOptions = facetOptions(regulatoryCatalog.data?.facets?.jurisdiction, [
    draft.regulatoryJurisdiction,
  ]);
  const regulatoryEventTypeOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.event_type,
    [draft.regulatoryEventType],
    eventTypeLabels,
  );
  const regulatoryStatusOptions = facetOptions(regulatoryCatalog.data?.facets?.status, [draft.regulatoryStatus]);
  const regulatoryDesignationOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.designation_type,
    [draft.regulatoryDesignationType],
    designationLabels,
  );
  const regulatoryLabelChangeOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.label_change_type,
    [draft.regulatoryLabelChangeType],
    labelChangeLabels,
  );
  const regulatoryBoxedWarningOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.has_boxed_warning,
    [draft.regulatoryBoxedWarning],
    boxedWarningLabels,
  );
  const regulatorySafetySignalOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_signal_type,
    [draft.regulatorySafetySignalType],
    safetySignalLabels,
  );
  const regulatorySafetySeverityOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_severity,
    [draft.regulatorySafetySeverity],
    severityLabels,
  );
  const regulatorySafetyStatusOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_status,
    [draft.regulatorySafetyStatus],
    safetyStatusLabels,
  );
  const regulatoryAdvancedConditionCount = [
    draft.regulatoryDesignationType,
    draft.regulatoryLabelChangeType,
    draft.regulatoryBoxedWarning,
    draft.regulatorySafetySignalType,
    draft.regulatorySafetySeverity,
    draft.regulatorySafetyStatus,
    draft.regulatorySourceUpdatedFrom,
    draft.regulatorySourceUpdatedTo,
  ].filter(Boolean).length;

  return {
    regulatoryCatalogState,
    regulatoryAgencyOptions,
    regulatoryJurisdictionOptions,
    regulatoryEventTypeOptions,
    regulatoryStatusOptions,
    regulatoryDesignationOptions,
    regulatoryLabelChangeOptions,
    regulatoryBoxedWarningOptions,
    regulatorySafetySignalOptions,
    regulatorySafetySeverityOptions,
    regulatorySafetyStatusOptions,
    regulatoryAdvancedConditionCount,
  };
}
