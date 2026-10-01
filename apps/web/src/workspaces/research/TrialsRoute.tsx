import { lazy } from "react";
import type { SortCriterion } from "../../lib/contracts/sorting";
import type { SortDirection as TrialSortDirection, TrialSortField } from "../../lib/contracts/trials";
import { workspaceUrl } from "../../lib/workspaceRouting";
import { trialReturnLabel, trialRoleGroupIds } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

const TrialsView = lazy(() => import("../../views/TrialsView").then((module) => ({ default: module.TrialsView })));

export function TrialsRoute({ context }: { context: ResearchRouteContext }) {
  const {
    location,
    activeTrialReturnLocation,
    navigate,
    openDrugById,
    openEntityById,
    openTargetById,
    openDiseaseById,
    openOrganizationById,
  } = context;
  return (
    <TrialsView
      displayMode={location.trialDisplayMode ?? "list"}
      analysisView={location.trialAnalysisView ?? "chart"}
      initialQuery={location.query}
      initialRegistry={location.registry ?? ""}
      initialStatus={location.trialStatus ?? ""}
      initialPhase={location.trialPhase ?? ""}
      initialStudyType={location.studyType ?? ""}
      initialAcronym={location.trialAcronym ?? ""}
      initialInitiationType={location.trialInitiationType ?? ""}
      initialTherapyLine={location.trialTherapyLine ?? ""}
      initialHasResults={location.trialHasResults ?? ""}
      initialResultEvaluation={location.trialResultEvaluation ?? ""}
      initialResultsPostedFrom={location.trialResultsPostedFrom ?? ""}
      initialResultsPostedTo={location.trialResultsPostedTo ?? ""}
      initialInvestigationalDrug={location.trialInvestigationalDrug ?? ""}
      initialCombinationDrug={location.trialCombinationDrug ?? ""}
      initialInvestigationalTarget={location.trialInvestigationalTarget ?? ""}
      initialCombinationTarget={location.trialCombinationTarget ?? ""}
      initialInvestigationalDrugEntityIds={trialRoleGroupIds(
        location,
        "investigational_drug",
        location.trialInvestigationalDrugEntityIds,
      )}
      initialCombinationDrugEntityIds={trialRoleGroupIds(
        location,
        "combination_drug",
        location.trialCombinationDrugEntityIds,
      )}
      initialInvestigationalTargetEntityIds={trialRoleGroupIds(
        location,
        "investigational_target",
        location.trialInvestigationalTargetEntityIds,
      )}
      initialCombinationTargetEntityIds={trialRoleGroupIds(
        location,
        "combination_target",
        location.trialCombinationTargetEntityIds,
      )}
      initialLinkedDrugModalities={location.trialLinkedDrugModalities ?? []}
      initialLinkedDrugInnovationTypes={location.trialLinkedDrugInnovationTypes ?? []}
      initialLinkedDrugCategories={location.trialLinkedDrugCategories ?? []}
      initialLinkedDrugProgramTags={location.trialLinkedDrugProgramTags ?? []}
      initialLinkedDrugGlobalPhase={location.trialLinkedDrugGlobalPhase ?? ""}
      initialLinkedDrugOrganizationCountryRegion={location.trialLinkedDrugOrganizationCountryRegion ?? ""}
      initialRoleEntityId={location.trialRoleEntityRole ? "" : (location.trialRoleEntityId ?? "")}
      initialRoleEntityIds={location.trialRoleEntityRole ? [] : (location.trialRoleEntityIds ?? [])}
      initialRoleEntityRole={location.trialRoleEntityRole ? "" : (location.trialRoleEntityRole ?? "")}
      initialHasKeyResult={location.trialHasKeyResult ?? ""}
      initialPublicationId={location.trialPublicationId ?? ""}
      initialConference={location.trialConference ?? ""}
      initialDisclosedFrom={location.trialDisclosedFrom ?? ""}
      initialDisclosedTo={location.trialDisclosedTo ?? ""}
      initialSortBy={(location.trialSortBy ?? "last_update_posted") as TrialSortField}
      initialSortDirection={(location.trialSortDirection ?? "desc") as TrialSortDirection}
      initialSort={location.trialSort as SortCriterion<TrialSortField>[] | undefined}
      initialOffset={location.offset ?? 0}
      selectedTrialId={location.trialId ?? null}
      activeSection={location.trialSection ?? "overview"}
      onSearchChange={(change) =>
        navigate({
          workbench: "research",
          view: "trials",
          query: change.query,
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
          registry: change.registry,
          trialStatus: change.status,
          trialPhase: change.phase,
          studyType: change.studyType,
          trialAcronym: change.acronym,
          trialInitiationType: change.initiationType,
          trialTherapyLine: change.therapyLine,
          trialHasResults: change.hasResults,
          trialResultEvaluation: change.resultEvaluation,
          trialResultsPostedFrom: change.resultsPostedFrom,
          trialResultsPostedTo: change.resultsPostedTo,
          trialInvestigationalDrug: change.investigationalDrug,
          trialCombinationDrug: change.combinationDrug,
          trialInvestigationalTarget: change.investigationalTarget,
          trialCombinationTarget: change.combinationTarget,
          trialInvestigationalDrugEntityIds: change.investigationalDrugEntityIds,
          trialCombinationDrugEntityIds: change.combinationDrugEntityIds,
          trialInvestigationalTargetEntityIds: change.investigationalTargetEntityIds,
          trialCombinationTargetEntityIds: change.combinationTargetEntityIds,
          trialLinkedDrugModalities: change.linkedDrugModalities,
          trialLinkedDrugInnovationTypes: change.linkedDrugInnovationTypes,
          trialLinkedDrugCategories: change.linkedDrugCategories,
          trialLinkedDrugProgramTags: change.linkedDrugProgramTags,
          trialLinkedDrugGlobalPhase: change.linkedDrugGlobalPhase,
          trialLinkedDrugOrganizationCountryRegion: change.linkedDrugOrganizationCountryRegion,
          trialRoleEntityId: change.roleEntityId,
          trialRoleEntityIds: change.roleEntityIds,
          trialRoleEntityRole: change.roleEntityRole,
          trialHasKeyResult: change.hasKeyResult,
          trialPublicationId: change.publicationId,
          trialConference: change.conference,
          trialDisclosedFrom: change.disclosedFrom,
          trialDisclosedTo: change.disclosedTo,
          trialSort: change.sort,
          trialSortBy: change.sortBy,
          trialSortDirection: change.sortDirection,
          trialDisplayMode: location.trialDisplayMode ?? "list",
          trialId: null,
          invalidTrialId: false,
          offset: change.offset,
        })
      }
      onTrialChange={(trialId) =>
        navigate(
          {
            ...location,
            trialId,
            invalidTrialId: false,
            trialSection: "overview",
          },
          trialId === null,
        )
      }
      returnLabel={trialReturnLabel(activeTrialReturnLocation)}
      onReturn={activeTrialReturnLocation ? () => navigate(activeTrialReturnLocation, true, true) : undefined}
      onSectionChange={(trialSection, replace = false) => navigate({ ...location, trialSection }, replace)}
      onOpenEntity={openEntityById}
      onOpenDrug={(entityId) => openDrugById(entityId, location.trialId ? workspaceUrl(location) : undefined)}
      onOpenTarget={(entityId) => openTargetById(entityId, location.trialId ? workspaceUrl(location) : undefined)}
      onOpenDisease={openDiseaseById}
      onOpenOrganization={openOrganizationById}
      onAnalysisViewChange={(trialAnalysisView) =>
        navigate({ ...location, trialAnalysisView, trialId: null, invalidTrialId: false })
      }
      onDisplayModeChange={(trialDisplayMode) =>
        navigate({ ...location, trialDisplayMode, trialId: null, invalidTrialId: false, offset: 0 })
      }
    />
  );
}
