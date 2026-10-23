import type { ClinicalTrialSearchResult } from "../../lib/generated";
import type { TrialFilterConditions, useTrialFilterDraft } from "./useTrialFilterDraft";
export interface TrialFilterProps {
  filters: TrialFilterConditions;
  setters: ReturnType<typeof useTrialFilterDraft>["setters"];
  data?: ClinicalTrialSearchResult;
  rememberRoleEntity: (id: string, name?: string) => void;
}
