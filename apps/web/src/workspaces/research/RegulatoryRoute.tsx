import { lazy } from "react";
import type { RegulatorySearchFilters } from "../../lib/contracts/regulatory";
import type { ResearchRouteContext } from "./routeContext";

const RegulatoryView = lazy(() =>
  import("../../views/RegulatoryView").then((module) => ({ default: module.RegulatoryView })),
);

export function RegulatoryRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <RegulatoryView
      initialFilters={{
        query: location.query,
        agency: location.regulatoryAgency ?? "",
        jurisdiction: location.regulatoryJurisdiction ?? "",
        eventType: location.regulatoryEventType ?? "",
        displayMode: location.regulatoryDisplayMode ?? "list",
        analysisView: location.regulatoryAnalysisView ?? "chart",
        status: location.regulatoryStatus ?? "",
        designationType: location.regulatoryDesignationType ?? "",
        labelChangeType: location.regulatoryLabelChangeType ?? "",
        boxedWarning: location.regulatoryBoxedWarning ?? "",
        safetySignalType: location.regulatorySafetySignalType ?? "",
        safetySeverity: location.regulatorySafetySeverity ?? "",
        safetyStatus: location.regulatorySafetyStatus ?? "",
        decisionFrom: location.regulatoryDecisionFrom ?? "",
        decisionTo: location.regulatoryDecisionTo ?? "",
        sourceUpdatedFrom: location.regulatorySourceUpdatedFrom ?? "",
        sourceUpdatedTo: location.regulatorySourceUpdatedTo ?? "",
        sortBy: (location.regulatorySortBy ?? "decision_date") as RegulatorySearchFilters["sortBy"],
        sortDirection: location.regulatorySortDirection ?? "desc",
        sort: location.regulatorySort as RegulatorySearchFilters["sort"],
      }}
      initialOffset={location.offset ?? 0}
      selectedEventId={location.regulatoryEventId ?? null}
      comparedEventIds={location.regulatoryCompareIds ?? []}
      onSearchChange={(filters, offset) =>
        navigate({
          ...location,
          query: filters.query,
          regulatoryAgency: filters.agency,
          regulatoryJurisdiction: filters.jurisdiction,
          regulatoryEventType: filters.eventType,
          regulatoryDisplayMode: filters.displayMode,
          regulatoryAnalysisView: filters.analysisView,
          regulatoryStatus: filters.status,
          regulatoryDesignationType: filters.designationType,
          regulatoryLabelChangeType: filters.labelChangeType,
          regulatoryBoxedWarning: filters.boxedWarning,
          regulatorySafetySignalType: filters.safetySignalType,
          regulatorySafetySeverity: filters.safetySeverity,
          regulatorySafetyStatus: filters.safetyStatus,
          regulatoryDecisionFrom: filters.decisionFrom,
          regulatoryDecisionTo: filters.decisionTo,
          regulatorySourceUpdatedFrom: filters.sourceUpdatedFrom,
          regulatorySourceUpdatedTo: filters.sourceUpdatedTo,
          regulatorySort: filters.sort,
          regulatorySortBy: filters.sortBy,
          regulatorySortDirection: filters.sortDirection,
          offset,
        })
      }
      onEventChange={(regulatoryEventId) =>
        navigate(
          {
            ...location,
            regulatoryEventId,
            invalidRegulatoryEventId: false,
          },
          regulatoryEventId === null,
        )
      }
      onCompareChange={(regulatoryCompareIds) => navigate({ ...location, regulatoryCompareIds })}
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
    />
  );
}
