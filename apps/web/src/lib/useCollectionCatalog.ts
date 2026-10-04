import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
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
  useEffect(() => {
    const page = query.data;
    if (!page || page.offset !== filter.offset) return;
    const lastOffset = Math.max(0, Math.ceil(page.total / page.limit) - 1) * page.limit;
    if (filter.offset > lastOffset)
      setFilter((current) =>
        current.q === filter.q && current.offset === page.offset ? { ...current, offset: lastOffset } : current,
      );
  }, [filter.offset, filter.q, query.data]);
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
