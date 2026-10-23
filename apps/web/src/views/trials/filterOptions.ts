import { facetOptions } from "../../lib/facets";
import type { ClinicalTrialSearchResult } from "../../lib/generated";
import { publicProgramTags } from "../../lib/programDisplay";
import type { TrialFilterConditions } from "./useTrialFilterDraft";
export function trialFilterOptions(data: ClinicalTrialSearchResult | undefined, filters: TrialFilterConditions) {
  const registries = facetOptions(data?.facets, "registry", filters.registry);
  const statuses = facetOptions(data?.facets, "overall_status", filters.status);
  const phases = facetOptions(data?.facets, "phase", filters.phase);
  const studyTypes = facetOptions(data?.facets, "study_type", filters.studyType);
  const linkedDrugModalityOptions = facetOptions(data?.facets, "linked_drug_modality", filters.linkedDrugModalities);
  const linkedDrugInnovationTypeOptions = facetOptions(
    data?.facets,
    "linked_drug_innovation_type",
    filters.linkedDrugInnovationTypes,
  );
  const linkedDrugCategoryOptions = facetOptions(data?.facets, "linked_drug_category", filters.linkedDrugCategories);
  const linkedDrugProgramTagOptions = publicProgramTags(
    facetOptions(data?.facets, "linked_drug_program_tag", filters.linkedDrugProgramTags),
  );
  const linkedDrugGlobalPhases = facetOptions(data?.facets, "linked_drug_global_phase", filters.linkedDrugGlobalPhase);
  const linkedDrugOrganizationCountries = facetOptions(
    data?.facets,
    "linked_drug_organization_country_region",
    filters.linkedDrugOrganizationCountryRegion,
  );

  return {
    registries,
    statuses,
    phases,
    studyTypes,
    linkedDrugModalityOptions,
    linkedDrugInnovationTypeOptions,
    linkedDrugCategoryOptions,
    linkedDrugProgramTagOptions,
    linkedDrugGlobalPhases,
    linkedDrugOrganizationCountries,
  };
}
