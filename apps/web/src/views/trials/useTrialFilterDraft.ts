import { type Dispatch, type SetStateAction, useMemo } from "react";
import type { TrialSavedSearchInput } from "../../lib/contracts/trials";
import { useFilterDraft } from "../../lib/useFilterDraft";
export type TrialFilterConditions = Omit<
  TrialSavedSearchInput,
  "sortBy" | "sortDirection" | "sort" | "displayMode" | "analysisView"
>;
export function useTrialFilterDraft(applied: TrialFilterConditions) {
  const [filters, setFilters] = useFilterDraft(applied);
  const setters = useMemo(() => {
    function bind<Key extends keyof TrialFilterConditions>(
      key: Key,
    ): Dispatch<SetStateAction<TrialFilterConditions[Key]>> {
      return (action) =>
        setFilters((current) => ({ ...current, [key]: typeof action === "function" ? action(current[key]) : action }));
    }
    return {
      setQuery: bind("query"),
      setRegistry: bind("registry"),
      setStatus: bind("status"),
      setPhase: bind("phase"),
      setStudyType: bind("studyType"),
      setAcronym: bind("acronym"),
      setInitiationType: bind("initiationType"),
      setTherapyLine: bind("therapyLine"),
      setHasResults: bind("hasResults"),
      setResultEvaluation: bind("resultEvaluation"),
      setResultsPostedFrom: bind("resultsPostedFrom"),
      setResultsPostedTo: bind("resultsPostedTo"),
      setInvestigationalDrug: bind("investigationalDrug"),
      setCombinationDrug: bind("combinationDrug"),
      setInvestigationalTarget: bind("investigationalTarget"),
      setCombinationTarget: bind("combinationTarget"),
      setInvestigationalDrugEntityIds: bind("investigationalDrugEntityIds"),
      setCombinationDrugEntityIds: bind("combinationDrugEntityIds"),
      setInvestigationalTargetEntityIds: bind("investigationalTargetEntityIds"),
      setCombinationTargetEntityIds: bind("combinationTargetEntityIds"),
      setLinkedDrugModalities: bind("linkedDrugModalities"),
      setLinkedDrugInnovationTypes: bind("linkedDrugInnovationTypes"),
      setLinkedDrugCategories: bind("linkedDrugCategories"),
      setLinkedDrugProgramTags: bind("linkedDrugProgramTags"),
      setLinkedDrugGlobalPhase: bind("linkedDrugGlobalPhase"),
      setLinkedDrugOrganizationCountryRegion: bind("linkedDrugOrganizationCountryRegion"),
      setRoleEntityId: bind("roleEntityId"),
      setRoleEntityIds: bind("roleEntityIds"),
      setRoleEntityRole: bind("roleEntityRole"),
      setHasKeyResult: bind("hasKeyResult"),
      setPublicationId: bind("publicationId"),
      setConference: bind("conference"),
      setDisclosedFrom: bind("disclosedFrom"),
      setDisclosedTo: bind("disclosedTo"),
    };
  }, [setFilters]);
  return { filters, setFilters, setters };
}
