import { useQueries, useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";
import type { KeyboardEvent } from "react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { getEntity, intelligenceKeys, lookupEntities } from "../lib/contracts/intelligence";
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

export function EntityMultiFilterSelect({
  label,
  entityType,
  values,
  onChange,
  onResolved,
  placeholder,
  maxSelections = 20,
}: {
  label: string;
  entityType: EntityType;
  values: string[];
  onChange: (entityIds: string[], selectedId?: string, selectedName?: string) => void;
  onResolved?: (entityId: string, displayName: string) => void;
  placeholder: string;
  maxSelections?: number;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const id = useId();
  const debouncedQuery = useDebouncedValue(query.trim(), 250);
  const selectedQueries = useQueries({
    queries: values.map((entityId) => ({
      queryKey: intelligenceKeys.entity(entityId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getEntity(entityId, signal),
    })),
  });
  const resolvedSelections = useMemo(
    () =>
      selectedQueries.flatMap((selected) =>
        selected.data && selected.data.entity_type === entityType
          ? [{ id: selected.data.id, name: selected.data.name }]
          : [],
      ),
    [entityType, selectedQueries],
  );
  const resolvedKey = resolvedSelections.map((item) => `${item.id}:${item.name}`).join("|");
  const emittedResolvedKey = useRef("");
  useEffect(() => {
    if (emittedResolvedKey.current === resolvedKey) return;
    emittedResolvedKey.current = resolvedKey;
    for (const item of resolvedSelections) onResolved?.(item.id, item.name);
  }, [onResolved, resolvedKey, resolvedSelections]);
  const options = useQuery({
    queryKey: intelligenceKeys.lookup(debouncedQuery, entityType),
    queryFn: ({ signal }) => lookupEntities(debouncedQuery, entityType, signal),
    enabled: values.length < maxSelections && debouncedQuery.length >= 2,
  });
  const availableOptions = (options.data ?? []).filter((entity) => !values.includes(entity.id));
  const listboxId = `${entityType}-multi-filter-options-${id.replaceAll(":", "")}`;
  const activeOptionId =
    activeIndex >= 0 && availableOptions[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined;
  useEffect(() => {
    if (!open || availableOptions.length === 0) {
      setActiveIndex(-1);
      return;
    }
    setActiveIndex((current) => (current >= availableOptions.length ? availableOptions.length - 1 : current));
  }, [availableOptions.length, open]);
  useEffect(() => {
    if (activeIndex < 0) return;
    optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [activeIndex]);

  function closeOptions() {
    setOpen(false);
    setActiveIndex(-1);
  }

  function selectCandidate(index: number) {
    const entity = availableOptions[index];
    if (!entity) return;
    onChange([...values, entity.id], entity.id, entity.name);
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
      if (availableOptions.length === 0) return;
      setActiveIndex((current) => {
        if (event.key === "ArrowDown") return current < availableOptions.length - 1 ? current + 1 : 0;
        return current > 0 ? current - 1 : availableOptions.length - 1;
      });
      return;
    }
    if (open && availableOptions.length > 0 && (event.key === "Home" || event.key === "End")) {
      event.preventDefault();
      setActiveIndex(event.key === "Home" ? 0 : availableOptions.length - 1);
      return;
    }
    if (open && event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectCandidate(activeIndex);
    }
  }

  return (
    <fieldset
      className="entity-filter-select entity-multi-filter-select"
      aria-label={`${label}多选`}
      onBlur={(event) => {
        if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
        closeOptions();
      }}
    >
      <span className="entity-filter-label">
        {label}
        {values.length ? (
          <small>
            {values.length}/{maxSelections}
          </small>
        ) : null}
      </span>
      {values.length ? (
        <fieldset className="entity-multi-filter-selections" aria-label={`已选${label}`}>
          {values.map((entityId, index) => {
            const selected = selectedQueries[index];
            const invalid = Boolean(selected?.error || (selected?.data && selected.data.entity_type !== entityType));
            return (
              <span className={`entity-filter-selection${invalid ? " invalid" : ""}`} key={entityId}>
                <span>
                  {selected?.isFetching
                    ? "正在读取实体"
                    : invalid
                      ? "所选实体不可用"
                      : selected?.data?.name || entityId}
                </span>
                <button
                  type="button"
                  onClick={() => onChange(values.filter((value) => value !== entityId))}
                  title={`移除${selected?.data?.name ?? entityId}`}
                  aria-label={`移除${selected?.data?.name ?? entityId}`}
                >
                  <X size={14} />
                </button>
              </span>
            );
          })}
        </fieldset>
      ) : null}
      {values.length < maxSelections ? (
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
            <div className="entity-filter-options" id={listboxId} role="listbox" aria-multiselectable="true">
              {options.isFetching ? <span>正在检索候选项</span> : null}
              {options.error ? <span className="error">实体检索暂不可用</span> : null}
              {availableOptions.map((entity, index) => (
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
              {!options.isFetching && !options.error && availableOptions.length === 0 ? (
                <span>未找到可添加项</span>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <span className="entity-filter-limit" role="status">
          已达到最多 {maxSelections} 项
        </span>
      )}
    </fieldset>
  );
}
