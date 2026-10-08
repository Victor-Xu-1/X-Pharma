import type { loadEpidemiologyFacetCatalog } from "../../../lib/contracts/epidemiology";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../../../lib/epidemiologyDisplay";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import { type FacetCatalogState, facetOptions, labeledFacetOptions } from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function epidemiologyOptions(
  draft: ProfessionalSearchDraft,
  epidemiologyCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadEpidemiologyFacetCatalog>>>,
) {
  const epidemiologyCatalogState: FacetCatalogState = epidemiologyCatalog.isPending
    ? "loading"
    : epidemiologyCatalog.isError
      ? "failed"
      : "ready";
  const epidemiologyMeasureOptions = labeledFacetOptions(
    epidemiologyCatalog.data?.facets?.measure,
    [draft.epidemiologyMeasure],
    epidemiologyMeasureLabels,
  );
  const epidemiologyGeographyOptions = facetOptions(epidemiologyCatalog.data?.facets?.geography, [
    draft.epidemiologyGeography,
  ]);
  const epidemiologyUnitOptions = facetOptions(epidemiologyCatalog.data?.facets?.unit, [draft.epidemiologyUnit]);
  const epidemiologyPopulationScopeOptions = facetOptions(epidemiologyCatalog.data?.facets?.population_scope, [
    draft.epidemiologyPopulationScope,
  ]);
  const epidemiologyAgeGroupOptions = facetOptions(epidemiologyCatalog.data?.facets?.age_group, [
    draft.epidemiologyAgeGroup,
  ]);
  const epidemiologySexOptions = labeledFacetOptions(
    epidemiologyCatalog.data?.facets?.sex,
    [draft.epidemiologySex],
    epidemiologySexLabels,
  );
  const epidemiologyPatientPopulationOptions = (epidemiologyCatalog.data?.patient_populations ?? [])
    .map((option) => ({ value: option.id, label: option.name, count: option.count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  if (
    draft.epidemiologyPatientPopulationId &&
    !epidemiologyPatientPopulationOptions.some((option) => option.value === draft.epidemiologyPatientPopulationId)
  ) {
    epidemiologyPatientPopulationOptions.push({
      value: draft.epidemiologyPatientPopulationId,
      label: draft.epidemiologyPatientPopulationId,
      count: 0,
    });
  }

  return {
    epidemiologyCatalogState,
    epidemiologyMeasureOptions,
    epidemiologyGeographyOptions,
    epidemiologyUnitOptions,
    epidemiologyPopulationScopeOptions,
    epidemiologyAgeGroupOptions,
    epidemiologySexOptions,
    epidemiologyPatientPopulationOptions,
  };
}
