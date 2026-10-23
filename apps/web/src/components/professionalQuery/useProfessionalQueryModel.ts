import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { dealKeys, loadDealFacetCatalog } from "../../lib/contracts/deals";
import { epidemiologyKeys, loadEpidemiologyFacetCatalog } from "../../lib/contracts/epidemiology";
import { loadNewsFacetCatalog, newsKeys } from "../../lib/contracts/news";
import { loadPatentFacetCatalog, patentKeys } from "../../lib/contracts/patents";
import { loadPipelineFacetCatalog, pipelineKeys } from "../../lib/contracts/pipeline";
import { loadRegulatoryFacetCatalog, regulatoryKeys } from "../../lib/contracts/regulatory";
import {
  countProfessionalConditions,
  createProfessionalSearchDraft,
  type PatentEntityType,
  type ProfessionalSearchDomain,
  type ProfessionalSearchDraft,
  professionalSearchLocation,
  validateProfessionalSearch,
} from "../../lib/professionalSearch";
import type { WorkspaceLocation } from "../../lib/workspaceRouting";
import { dealsOptions } from "./options/deals";
import { epidemiologyOptions } from "./options/epidemiology";
import { newsOptions } from "./options/news";
import { patentsOptions } from "./options/patents";
import { pipelineOptions } from "./options/pipeline";
import { regulatoryOptions } from "./options/regulatory";
import { trialsOptions } from "./options/trials";
import { domains } from "./presentation";

/** Sole owner of draft, catalog reads, validation and query execution. */
export function useProfessionalQueryModel(query: string, onExecute: (location: WorkspaceLocation) => void) {
  const [draft, setDraft] = useState(() => createProfessionalSearchDraft("pipeline", query));
  const [error, setError] = useState("");
  const pipelineCatalog = useQuery({
    queryKey: pipelineKeys.facetCatalog(),
    queryFn: ({ signal }) => loadPipelineFacetCatalog(signal),
    enabled: draft.domain === "pipeline",
    staleTime: 5 * 60 * 1000,
  });
  const patentCatalog = useQuery({
    queryKey: patentKeys.facetCatalog(),
    queryFn: ({ signal }) => loadPatentFacetCatalog(signal),
    enabled: draft.domain === "patents",
    staleTime: 5 * 60 * 1000,
  });
  const dealCatalog = useQuery({
    queryKey: dealKeys.facetCatalog(),
    queryFn: ({ signal }) => loadDealFacetCatalog(signal),
    enabled: draft.domain === "deals",
    staleTime: 5 * 60 * 1000,
  });
  const regulatoryCatalog = useQuery({
    queryKey: regulatoryKeys.facetCatalog(),
    queryFn: ({ signal }) => loadRegulatoryFacetCatalog(signal),
    enabled: draft.domain === "regulatory",
    staleTime: 5 * 60 * 1000,
  });
  const epidemiologyCatalog = useQuery({
    queryKey: epidemiologyKeys.facetCatalog(),
    queryFn: ({ signal }) => loadEpidemiologyFacetCatalog(signal),
    enabled: draft.domain === "epidemiology",
    staleTime: 5 * 60 * 1000,
  });
  const newsCatalog = useQuery({
    queryKey: newsKeys.facetCatalog(),
    queryFn: ({ signal }) => loadNewsFacetCatalog(signal),
    enabled: draft.domain === "news",
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    setDraft((current) => ({ ...current, query }));
  }, [query]);

  function update<K extends keyof ProfessionalSearchDraft>(key: K, value: ProfessionalSearchDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setError("");
  }

  function updateDateRange(
    fromKey: keyof ProfessionalSearchDraft,
    toKey: keyof ProfessionalSearchDraft,
    from: string,
    to: string,
  ) {
    setDraft((current) => ({ ...current, [fromKey]: from, [toKey]: to }));
    setError("");
  }

  function selectDomain(domain: ProfessionalSearchDomain) {
    setDraft(createProfessionalSearchDraft(domain, query));
    setError("");
  }

  function updatePatentEntityType(entityType: PatentEntityType) {
    setDraft((current) => ({ ...current, patentEntityType: entityType, patentEntityId: "" }));
    setError("");
  }

  function execute() {
    const validationError = validateProfessionalSearch(draft);
    if (validationError) {
      setError(validationError);
      return;
    }
    onExecute(professionalSearchLocation(draft));
  }

  const selected = domains.find((item) => item.value === draft.domain) ?? domains[0];
  const conditionCount = countProfessionalConditions(draft);

  return {
    pipelineCatalog,
    patentCatalog,
    dealCatalog,
    regulatoryCatalog,
    epidemiologyCatalog,
    newsCatalog,
    selected,
    conditionCount,
    draft,
    setDraft,
    error,
    setError,
    update,
    updateDateRange,
    selectDomain,
    updatePatentEntityType,
    execute,
    ...pipelineOptions(draft, pipelineCatalog),
    ...trialsOptions(draft),
    ...patentsOptions(draft, patentCatalog),
    ...dealsOptions(draft, dealCatalog),
    ...regulatoryOptions(draft, regulatoryCatalog),
    ...epidemiologyOptions(draft, epidemiologyCatalog),
    ...newsOptions(draft, newsCatalog),
  };
}
export type ProfessionalQueryModel = ReturnType<typeof useProfessionalQueryModel>;
