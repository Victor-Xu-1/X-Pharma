import { type loadPatentFacetCatalog, patentLegalStatusLabels } from "../../../lib/contracts/patents";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import { type FacetCatalogState, labeledFacetOptions } from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function patentsOptions(
  draft: ProfessionalSearchDraft,
  patentCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadPatentFacetCatalog>>>,
) {
  const patentCatalogState: FacetCatalogState = patentCatalog.isPending
    ? "loading"
    : patentCatalog.isError
      ? "failed"
      : "ready";
  const patentLegalStatusOptions = labeledFacetOptions(
    patentCatalog.data?.facets?.legal_status,
    [draft.legalStatus],
    patentLegalStatusLabels,
  );

  return { patentCatalogState, patentLegalStatusOptions };
}
