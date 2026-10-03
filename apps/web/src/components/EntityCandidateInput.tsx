import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { type FocusEvent, type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import {
  type IntelligenceEntity,
  intelligenceKeys,
  lookupEntities,
  lookupEntityTypes,
} from "../lib/contracts/intelligence";
import type { EntityType } from "../lib/generated";
import { EntitySearchOption } from "./EntitySearchOption";

export function EntityCandidateInput({
  label,
  entityTypes,
  excludedIds = [],
  onSelect,
  placeholder,
  multiple = false,
}: {
  label: string;
  entityTypes: readonly EntityType[];
  excludedIds?: readonly string[];
  onSelect: (entity: IntelligenceEntity) => void;
  placeholder: string;
  multiple?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const groupRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listboxId = `entity-candidates-${useId().replaceAll(":", "")}`;
  const normalizedQuery = query.trim();
  const queryReady = normalizedQuery === debouncedQuery && normalizedQuery.length >= 2;
  const expanded = open && normalizedQuery.length >= 2;

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(normalizedQuery), 250);
    return () => window.clearTimeout(timer);
  }, [normalizedQuery]);

  const options = useQuery({
    queryKey:
      entityTypes.length === 1
        ? intelligenceKeys.lookup(debouncedQuery, entityTypes[0])
        : intelligenceKeys.lookupMany(debouncedQuery, entityTypes),
    queryFn: ({ signal }) =>
      entityTypes.length === 1
        ? lookupEntities(debouncedQuery, entityTypes[0], signal)
        : lookupEntityTypes(debouncedQuery, entityTypes, signal),
    enabled: expanded && queryReady,
  });
  const invalidCandidates = Boolean(
    queryReady && options.data?.some((entity) => !entityTypes.includes(entity.entity_type)),
  );
  const pending = !queryReady || options.isPending || options.isFetching;
  const failed = options.isError || invalidCandidates;
  const candidates = useMemo(
    () =>
      queryReady && !pending && !failed
        ? (options.data ?? []).filter((entity) => !excludedIds.includes(entity.id))
        : [],
    [excludedIds, failed, options.data, pending, queryReady],
  );
  const activeOptionId =
    expanded && activeIndex >= 0 && candidates[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined;

  useEffect(() => {
    if (!expanded || candidates.length === 0) {
      setActiveIndex(-1);
      return;
    }
    setActiveIndex((current) => (current >= candidates.length ? candidates.length - 1 : current));
  }, [candidates.length, expanded]);

  useEffect(() => {
    if (activeIndex >= 0) optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex]);

  function closeOptions() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function closeOnBlur(event: FocusEvent<HTMLElement>) {
    if (event.relatedTarget instanceof Node && groupRef.current?.contains(event.relatedTarget)) return;
    closeOptions();
  }

  function retryLookup() {
    inputRef.current?.focus();
    void options.refetch();
  }

  function selectCandidate(index: number) {
    const entity = candidates[index];
    if (!entity || !queryReady || pending || failed) return;
    onSelect(entity);
    setQuery("");
    closeOptions();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      if (expanded) {
        event.preventDefault();
        event.stopPropagation();
      }
      closeOptions();
      return;
    }
    if (event.key === "Enter") {
      // This input selects a canonical ID; blank, short or dismissed terms must
      // never trigger the surrounding query form's implicit submit.
      event.preventDefault();
      if (expanded && activeIndex >= 0) selectCandidate(activeIndex);
      return;
    }
    if (normalizedQuery.length < 2) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (!candidates.length) return;
      setActiveIndex((current) =>
        event.key === "ArrowDown"
          ? current < candidates.length - 1
            ? current + 1
            : 0
          : current > 0
            ? current - 1
            : candidates.length - 1,
      );
    } else if (expanded && candidates.length && (event.key === "Home" || event.key === "End")) {
      event.preventDefault();
      setActiveIndex(event.key === "Home" ? 0 : candidates.length - 1);
    }
  }

  return (
    <div className="entity-filter-combobox" ref={groupRef}>
      <Search size={15} aria-hidden="true" />
      <input
        ref={inputRef}
        value={query}
        maxLength={240}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
          setActiveIndex(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={closeOnBlur}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label={`${label}筛选`}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
      />
      {expanded ? (
        <div className="entity-filter-options">
          {pending ? <span role="status">正在检索候选项</span> : null}
          {!pending && failed ? (
            <div role="alert">
              <span className="error">实体检索暂不可用，请重试</span>
              <button type="button" onBlur={closeOnBlur} onClick={retryLookup} aria-label={`重试${label}候选检索`}>
                重新检索
              </button>
            </div>
          ) : null}
          <div id={listboxId} role="listbox" aria-label={`${label}候选项`} aria-multiselectable={multiple || undefined}>
            {candidates.map((entity, index) => (
              <button
                type="button"
                role="option"
                id={`${listboxId}-option-${index}`}
                aria-selected={activeIndex === index}
                className={activeIndex === index ? "active" : ""}
                tabIndex={-1}
                ref={(node) => {
                  optionRefs.current[index] = node;
                }}
                key={entity.id}
                onMouseEnter={() => setActiveIndex(index)}
                onBlur={closeOnBlur}
                onClick={() => selectCandidate(index)}
              >
                <EntitySearchOption entity={entity} />
              </button>
            ))}
          </div>
          {!pending && !failed && candidates.length === 0 ? (
            <span role="status">{multiple ? "未找到可添加项" : "未找到匹配项"}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
