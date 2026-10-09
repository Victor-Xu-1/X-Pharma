import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../../lib/api";
import { loadTrialDetail, searchTrials, type TrialSavedSearchInput, trialKeys } from "../../lib/contracts/trials";

function readableData<Data>(data: Data | undefined, error: Error | null): Data | undefined {
  return error instanceof ApiError && [401, 403].includes(error.status) ? undefined : data;
}
export function useTrialQueries(input: TrialSavedSearchInput, offset: number, selectedTrialId: string | null) {
  const args = [
    input.query,
    input.registry,
    input.status,
    input.phase,
    input.studyType,
    input.acronym,
    input.initiationType,
    input.therapyLine,
    input.hasResults,
    input.resultEvaluation,
    input.resultsPostedFrom,
    input.resultsPostedTo,
    input.investigationalDrug,
    input.combinationDrug,
    input.investigationalTarget,
    input.combinationTarget,
    input.investigationalDrugEntityIds,
    input.combinationDrugEntityIds,
    input.investigationalTargetEntityIds,
    input.combinationTargetEntityIds,
    input.linkedDrugModalities,
    input.linkedDrugInnovationTypes,
    input.linkedDrugCategories,
    input.linkedDrugProgramTags,
    input.linkedDrugGlobalPhase,
    input.linkedDrugOrganizationCountryRegion,
    input.roleEntityId,
    input.roleEntityIds,
    input.roleEntityRole,
    input.hasKeyResult,
    input.publicationId,
    input.conference,
    input.disclosedFrom,
    input.disclosedTo,
    input.sortBy,
    input.sortDirection,
    offset,
  ] as const;
  const resultQueryKey = trialKeys.search(...args, input.sort);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchTrials(...args, signal, input.sort),
    enabled: selectedTrialId === null,
  });
  const detail = useQuery({
    queryKey: trialKeys.detail(selectedTrialId ?? ""),
    queryFn: ({ signal }) => loadTrialDetail(selectedTrialId ?? "", signal),
    enabled: selectedTrialId !== null,
  });
  return {
    resultQueryKey,
    result,
    detail,
    resultData: readableData(result.data, result.error),
    detailData: readableData(detail.data, detail.error),
  };
}
