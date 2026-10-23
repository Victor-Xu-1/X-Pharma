import { facetOptions } from "../../lib/facets";
import { pipelineResultEvaluationLabels as resultEvaluationLabels } from "../../lib/pipelineSignals";
import { publicProgramTags } from "../../lib/programDisplay";
import type { PipelineFilterProps } from "./filterTypes";
export function pipelineFilterOptions(data: PipelineFilterProps["data"], filters: PipelineFilterProps["filters"]) {
  const modalities = facetOptions(data?.facets, "modality", filters.modalities);
  const innovationTypes = facetOptions(data?.facets, "innovation_type", filters.innovationTypes);
  const therapeuticAreas = facetOptions(data?.facets, "therapeutic_area", filters.therapeuticAreas);
  const drugCategories = facetOptions(data?.facets, "drug_category", filters.drugCategories);
  const phases = facetOptions(data?.facets, "phase", filters.phase);
  const geographies = facetOptions(data?.facets, "geography", filters.geography);
  const globalPhases = facetOptions(data?.facets, "global_phase", filters.globalPhase);
  const chinaPhases = facetOptions(data?.facets, "china_phase", filters.chinaPhase);
  const developmentRights = facetOptions(data?.facets, "development_rights_region", filters.developmentRightsRegion);
  const commercializationRights = facetOptions(
    data?.facets,
    "commercialization_rights_region",
    filters.commercializationRightsRegion,
  );
  const programTags = publicProgramTags(facetOptions(data?.facets, "program_tag", filters.programTags));
  const milestoneTypes = facetOptions(data?.facets, "milestone_type", filters.milestoneType);
  const resultEvaluations = Object.keys(resultEvaluationLabels);
  const dealCurrencies = facetOptions(data?.facets, "deal_currency", filters.dealCurrency);
  const organizationTypes = facetOptions(data?.facets, "organization_type", filters.organizationType);
  const organizationCountries = facetOptions(
    data?.facets,
    "organization_country_region",
    filters.organizationCountryRegion,
  );
  return {
    modalities,
    innovationTypes,
    therapeuticAreas,
    drugCategories,
    phases,
    geographies,
    globalPhases,
    chinaPhases,
    developmentRights,
    commercializationRights,
    programTags,
    milestoneTypes,
    resultEvaluations,
    dealCurrencies,
    organizationTypes,
    organizationCountries,
  };
}
