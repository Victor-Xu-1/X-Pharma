import { lazy } from "react";
import type { SortDirection as PatentSortDirection, PatentSortField } from "../../lib/contracts/patents";
import type { SortCriterion } from "../../lib/contracts/sorting";
import type { ResearchRouteContext } from "./routeContext";

const PatentsView = lazy(() => import("../../views/PatentsView").then((module) => ({ default: module.PatentsView })));

export function PatentsRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openDrugById, openEntityById, openTargetById, openDiseaseById, openOrganizationById } =
    context;
  return (
    <PatentsView
      initialQuery={location.query}
      initialEntityId={location.patentEntityId ?? ""}
      initialApplicant={location.applicant ?? ""}
      initialLegalStatus={location.legalStatus ?? ""}
      initialPriorityFrom={location.patentPriorityFrom ?? ""}
      initialPriorityTo={location.patentPriorityTo ?? ""}
      initialExpirationFrom={location.patentExpirationFrom ?? ""}
      initialExpirationTo={location.patentExpirationTo ?? ""}
      initialSortBy={(location.patentSortBy ?? "priority_date") as PatentSortField}
      initialSortDirection={(location.patentSortDirection ?? "desc") as PatentSortDirection}
      initialSort={location.patentSort as SortCriterion<PatentSortField>[] | undefined}
      initialOffset={location.offset ?? 0}
      displayMode={location.patentDisplayMode ?? "list"}
      analysisView={location.patentAnalysisView ?? "chart"}
      onDisplayModeChange={(patentDisplayMode) =>
        navigate({ ...location, patentDisplayMode, patentId: null, invalidPatentId: false, offset: 0 })
      }
      onAnalysisViewChange={(patentAnalysisView) =>
        navigate({ ...location, patentAnalysisView, patentId: null, invalidPatentId: false })
      }
      selectedPatentId={location.patentId ?? null}
      activeSection={location.patentSection ?? "overview"}
      onSearchChange={(input, offset) =>
        navigate({
          workbench: "research",
          view: "patents",
          query: input.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          patentEntityId: input.entityId,
          applicant: input.applicant,
          legalStatus: input.legalStatus,
          patentPriorityFrom: input.priorityFrom,
          patentPriorityTo: input.priorityTo,
          patentExpirationFrom: input.expirationFrom,
          patentExpirationTo: input.expirationTo,
          patentSort: input.sort,
          patentSortBy: input.sortBy,
          patentSortDirection: input.sortDirection,
          patentDisplayMode: input.displayMode,
          patentAnalysisView: input.analysisView,
          patentId: null,
          invalidPatentId: false,
          offset,
        })
      }
      onPatentChange={(patentId) =>
        navigate(
          {
            ...location,
            patentId,
            invalidPatentId: false,
            patentSection: "overview",
          },
          patentId === null,
        )
      }
      onSectionChange={(patentSection, replace = false) => navigate({ ...location, patentSection }, replace)}
      onOpenEntity={openEntityById}
      onOpenDrug={openDrugById}
      onOpenTarget={openTargetById}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
    />
  );
}
