import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { collectionsKeys, loadCollectionCatalog } from "./contracts/collections";

export function useCollectionCatalog(enabled = true, editableOnly = false) {
  const [draft, setDraft] = useState("");
  const [filter, setFilter] = useState({ q: "", offset: 0 });
  const query = useQuery({
    queryKey: collectionsKeys.catalog(filter.q, filter.offset, editableOnly),
    queryFn: ({ signal }) =>
      editableOnly
        ? loadCollectionCatalog(filter.q, filter.offset, signal, true)
        : loadCollectionCatalog(filter.q, filter.offset, signal),
    enabled,
  });
  function search(event?: FormEvent) {
    event?.preventDefault();
    setFilter({ q: draft.trim(), offset: 0 });
  }
  return {
    query,
    draft,
    setDraft,
    filter,
    search,
    changePage: (offset: number) => setFilter((current) => ({ ...current, offset })),
  };
}
