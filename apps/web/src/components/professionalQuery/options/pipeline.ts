import type { loadPipelineFacetCatalog } from "../../../lib/contracts/pipeline";
import { pipelineBooleanSignalLabels, pipelineResultEvaluationLabels } from "../../../lib/pipelineSignals";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import {
  type FacetCatalogState,
  facetOptions,
  labeledFacetOptions,
  pipelineOrganizationRoleLabels,
  pipelineProgramStatusLabels,
} from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function pipelineOptions(
  draft: ProfessionalSearchDraft,
  pipelineCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadPipelineFacetCatalog>>>,
) {
  const pipelineAdvancedConditionCount =
    draft.pipelineProgramTags.length +
    [
      draft.pipelineGlobalPhase,
      draft.pipelineChinaPhase,
      draft.pipelineGlobalPhaseStartedFrom,
      draft.pipelineGlobalPhaseStartedTo,
      draft.pipelineChinaPhaseStartedFrom,
      draft.pipelineChinaPhaseStartedTo,
      draft.pipelineDevelopmentRightsRegion,
      draft.pipelineCommercializationRightsRegion,
      draft.pipelineOrganizationRole,
      draft.pipelineOrganizationType,
      draft.pipelineOrganizationCountryRegion,
      draft.pipelineMilestoneType,
      draft.pipelineMilestoneFrom,
      draft.pipelineMilestoneTo,
    ].filter(Boolean).length;
  const pipelineSignalConditionCount = [
    draft.pipelineHasClinicalResults,
    draft.pipelineClinicalResultEvaluation,
    draft.pipelineHasDeal,
    draft.pipelineDealCurrency,
    draft.pipelineDealTotalPotentialAmountMin,
    draft.pipelineDealTotalPotentialAmountMax,
  ].filter(Boolean).length;
  const pipelineCatalogState: FacetCatalogState = pipelineCatalog.isPending
    ? "loading"
    : pipelineCatalog.isError
      ? "failed"
      : "ready";
  const modalityOptions = facetOptions(pipelineCatalog.data?.facets?.modality, draft.modalities);
  const innovationTypeOptions = facetOptions(
    pipelineCatalog.data?.facets?.innovation_type,
    draft.pipelineInnovationTypes,
  );
  const therapeuticAreaOptions = facetOptions(
    pipelineCatalog.data?.facets?.therapeutic_area,
    draft.pipelineTherapeuticAreas,
  );
  const drugCategoryOptions = facetOptions(pipelineCatalog.data?.facets?.drug_category, draft.pipelineDrugCategories);
  const programStatusOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.program_status,
    [draft.pipelineProgramStatus],
    pipelineProgramStatusLabels,
  );
  const organizationRoleOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.organization_role,
    [draft.pipelineOrganizationRole],
    pipelineOrganizationRoleLabels,
  );
  const organizationTypeOptions = facetOptions(pipelineCatalog.data?.facets?.organization_type, [
    draft.pipelineOrganizationType,
  ]);
  const organizationCountryOptions = facetOptions(pipelineCatalog.data?.facets?.organization_country_region, [
    draft.pipelineOrganizationCountryRegion,
  ]);
  const geographyOptions = facetOptions(pipelineCatalog.data?.facets?.geography, [draft.geography]);
  const developmentRightsOptions = facetOptions(pipelineCatalog.data?.facets?.development_rights_region, [
    draft.pipelineDevelopmentRightsRegion,
  ]);
  const commercializationRightsOptions = facetOptions(pipelineCatalog.data?.facets?.commercialization_rights_region, [
    draft.pipelineCommercializationRightsRegion,
  ]);
  const programTagOptions = facetOptions(pipelineCatalog.data?.facets?.program_tag, draft.pipelineProgramTags);
  const milestoneTypeOptions = facetOptions(pipelineCatalog.data?.facets?.milestone_type, [
    draft.pipelineMilestoneType,
  ]);
  const clinicalResultPresenceOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.has_clinical_results,
    [draft.pipelineHasClinicalResults],
    pipelineBooleanSignalLabels,
  );
  const clinicalResultEvaluationOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.clinical_result_evaluation,
    [draft.pipelineClinicalResultEvaluation],
    pipelineResultEvaluationLabels,
  );
  const dealPresenceOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.has_deal,
    [draft.pipelineHasDeal],
    pipelineBooleanSignalLabels,
  );
  const pipelineDealCurrencyOptions = facetOptions(pipelineCatalog.data?.facets?.deal_currency, [
    draft.pipelineDealCurrency,
  ]);

  return {
    pipelineAdvancedConditionCount,
    pipelineSignalConditionCount,
    pipelineCatalogState,
    modalityOptions,
    innovationTypeOptions,
    therapeuticAreaOptions,
    drugCategoryOptions,
    programStatusOptions,
    organizationRoleOptions,
    organizationTypeOptions,
    organizationCountryOptions,
    geographyOptions,
    developmentRightsOptions,
    commercializationRightsOptions,
    programTagOptions,
    milestoneTypeOptions,
    clinicalResultPresenceOptions,
    clinicalResultEvaluationOptions,
    dealPresenceOptions,
    pipelineDealCurrencyOptions,
  };
}
