import { lazy } from "react";
import type { EpidemiologyFilters } from "../../lib/contracts/epidemiology";
import type { ResearchRouteContext } from "./routeContext";

const EpidemiologyView = lazy(() =>
  import("../../views/EpidemiologyView").then((module) => ({ default: module.EpidemiologyView })),
);

export function EpidemiologyRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <EpidemiologyView
      initialFilters={{
        query: location.query,
        diseaseEntityId: location.epidemiologyDiseaseEntityId ?? "",
        measure: location.epidemiologyMeasure ?? "",
        geography: location.epidemiologyGeography ?? "",
        unit: location.epidemiologyUnit ?? "",
        patientPopulationId: location.epidemiologyPatientPopulationId ?? "",
        populationScope: location.epidemiologyPopulationScope ?? "",
        ageGroup: location.epidemiologyAgeGroup ?? "",
        sex: location.epidemiologySex ?? "",
        periodStartFrom: location.epidemiologyPeriodStartFrom ?? "",
        periodEndTo: location.epidemiologyPeriodEndTo ?? "",
        sortBy: (location.epidemiologySortBy ?? "period_end") as EpidemiologyFilters["sortBy"],
        sortDirection: location.epidemiologySortDirection ?? "desc",
        sort: location.epidemiologySort as EpidemiologyFilters["sort"],
        displayMode: location.epidemiologyDisplayMode ?? "list",
        analysisView: location.epidemiologyAnalysisView ?? "chart",
      }}
      initialOffset={location.offset ?? 0}
      onSearchChange={(filters, offset) =>
        navigate({
          workbench: "research",
          view: "epidemiology",
          query: filters.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          epidemiologyDiseaseEntityId: filters.diseaseEntityId,
          epidemiologyMeasure: filters.measure,
          epidemiologyDisplayMode: filters.displayMode,
          epidemiologyAnalysisView: filters.analysisView,
          epidemiologyGeography: filters.geography,
          epidemiologyUnit: filters.unit,
          epidemiologyPatientPopulationId: filters.patientPopulationId,
          epidemiologyPopulationScope: filters.populationScope,
          epidemiologyAgeGroup: filters.ageGroup,
          epidemiologySex: filters.sex,
          epidemiologyPeriodStartFrom: filters.periodStartFrom,
          epidemiologyPeriodEndTo: filters.periodEndTo,
          epidemiologySort: filters.sort,
          epidemiologySortBy: filters.sortBy,
          epidemiologySortDirection: filters.sortDirection,
          offset,
        })
      }
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
    />
  );
}
