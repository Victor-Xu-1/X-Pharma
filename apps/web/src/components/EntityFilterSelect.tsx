import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { getEntity, intelligenceKeys, lookupEntities, lookupEntityTypes } from "../lib/contracts/intelligence";
import type { EntityType } from "../lib/generated";
import { EntitySearchOption } from "./EntitySearchOption";

function useDebouncedValue(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

export function EntityFilterSelect({
  label,
  entityType,
  value,
  onChange,
  onResolved,
  placeholder,
}: {
  label: string;
  entityType: EntityType | readonly EntityType[];
  value: string;
  onChange: (entityId: string, displayName?: string) => void;
  onResolved?: (entityId: string, displayName: string) => void;
  placeholder: string;
}) {
  const entityTypes = useMemo(() => (Array.isArray(entityType) ? [...entityType] : [entityType]), [entityType]);
  const entityTypeKey = entityTypes.join("-");
  const instanceId = useId().replace(/:/g, "");
  const listboxId = `${entityTypeKey}-filter-options-${instanceId}`;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const debouncedQuery = useDebouncedValue(query.trim(), 250);
  const selected = useQuery({
    queryKey: intelligenceKeys.entity(value),
    queryFn: ({ signal }) => getEntity(value, signal),
    enabled: Boolean(value),
  });
  const options = useQuery({
    queryKey:
      entityTypes.length === 1
        ? intelligenceKeys.lookup(debouncedQuery, entityTypes[0])
        : intelligenceKeys.lookupMany(debouncedQuery, entityTypes),
    queryFn: ({ signal }) =>
      entityTypes.length === 1
        ? lookupEntities(debouncedQuery, entityTypes[0], signal)
        : lookupEntityTypes(debouncedQuery, entityTypes, signal),
    enabled: !value && debouncedQuery.length >= 2,
  });
  const candidates = options.data ?? [];
  const activeOptionId = activeIndex >= 0 && candidates[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined;
  const invalidSelection = selected.data && !entityTypes.includes(selected.data.entity_type);
  useEffect(() => {
    if (selected.data && entityTypes.includes(selected.data.entity_type)) {
      onResolved?.(selected.data.id, selected.data.name);
    }
  }, [entityTypes, onResolved, selected.data]);
  useEffect(() => {
    if (!open || candidates.length === 0) {
      setActiveIndex(-1);
      return;
    }
    setActiveIndex((current) => (current >= candidates.length ? candidates.length - 1 : current));
  }, [candidates.length, open]);
  useEffect(() => {
    if (activeIndex < 0) return;
    optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex]);

  function closeOptions() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function selectCandidate(index: number) {
    const entity = candidates[index];
    if (!entity) return;
    onChange(entity.id, entity.name);
    setQuery("");
    closeOptions();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      if (open) event.preventDefault();
      closeOptions();
      return;
    }
    if (debouncedQuery.length < 2) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (candidates.length === 0) return;
      setActiveIndex((current) => {
        if (event.key === "ArrowDown") return current < candidates.length - 1 ? current + 1 : 0;
        return current > 0 ? current - 1 : candidates.length - 1;
      });
      return;
    }
    if (open && candidates.length > 0 && (event.key === "Home" || event.key === "End")) {
      event.preventDefault();
      setActiveIndex(event.key === "Home" ? 0 : candidates.length - 1);
      return;
    }
    if (open && event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectCandidate(activeIndex);
    }
  }

  return (
    <fieldset
      className="entity-filter-select"
      aria-label={`${label}检索与选择`}
      onBlur={(event) => {
        if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
        closeOptions();
      }}
    >
      <span className="entity-filter-label">{label}</span>
      {value ? (
        <div className={`entity-filter-selection${invalidSelection || selected.error ? " invalid" : ""}`}>
          <span>
            {selected.isFetching
              ? "正在读取实体"
              : invalidSelection || selected.error
                ? "所选实体不可用"
                : selected.data?.name || value}
          </span>
          <button type="button" onClick={() => onChange("")} title={`清除${label}`} aria-label={`清除${label}`}>
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className="entity-filter-combobox">
          <Search size={15} />
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
              setActiveIndex(-1);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            aria-label={`${label}筛选`}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={open && debouncedQuery.length >= 2}
            aria-controls={listboxId}
            aria-activedescendant={activeOptionId}
          />
          {open && debouncedQuery.length >= 2 ? (
            <div className="entity-filter-options" id={listboxId} role="listbox">
              {options.isFetching ? <span>正在检索候选项</span> : null}
              {options.error ? <span className="error">实体检索暂不可用</span> : null}
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
                  onClick={() => selectCandidate(index)}
                >
                  <EntitySearchOption entity={entity} />
                </button>
              ))}
              {!options.isFetching && !options.error && candidates.length === 0 ? <span>未找到匹配项</span> : null}
            </div>
          ) : null}
        </div>
      )}
    </fieldset>
  );
}
