import type { loadNewsFacetCatalog } from "../../../lib/contracts/news";
import { newsEventTypeLabels, newsLanguageLabels } from "../../../lib/newsDisplay";
import type { ProfessionalSearchDraft } from "../../../lib/professionalSearch";
import { type FacetCatalogState, facetOptions, labeledFacetOptions } from "../presentation";
import type { CatalogSnapshot } from "./types";

/** Derived governed options only; no state or request authority. */
export function newsOptions(
  draft: ProfessionalSearchDraft,
  newsCatalog: CatalogSnapshot<Awaited<ReturnType<typeof loadNewsFacetCatalog>>>,
) {
  const newsCatalogState: FacetCatalogState = newsCatalog.isPending
    ? "loading"
    : newsCatalog.isError
      ? "failed"
      : "ready";
  const newsEventTypeOptions = labeledFacetOptions(
    newsCatalog.data?.facets?.event_type,
    [draft.newsEventType],
    newsEventTypeLabels,
  );
  const newsPublisherOptions = facetOptions(newsCatalog.data?.facets?.publisher, [draft.newsPublisher]);
  const newsLanguageOptions = labeledFacetOptions(
    newsCatalog.data?.facets?.language,
    [draft.newsLanguage],
    newsLanguageLabels,
  );
  const newsVenueOptions = facetOptions(newsCatalog.data?.facets?.venue, [draft.newsVenue]);

  return { newsCatalogState, newsEventTypeOptions, newsPublisherOptions, newsLanguageOptions, newsVenueOptions };
}
