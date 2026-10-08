import { hashKey, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { type KeyboardEvent, type Ref, useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import { intelligenceKeys, suggestEntities } from "../lib/contracts/intelligence";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";
import { useFocusDismissal } from "../lib/useFocusDismissal";
import { useSearchShortcut } from "../lib/useSearchShortcut";

/** Name suggestions are optional; an unselected Enter always submits the typed search. */
export function EntitySearchInput({
  query,
  entityTypes,
  domainLabel,
  onQueryChange,
  onSearch,
  controlRef,
}: {
  query: string;
  entityTypes: string[];
  domainLabel: string;
  onQueryChange: (value: string) => void;
  onSearch: (value: string) => void;
  controlRef?: Ref<{ close: () => void }>;
}) {
  useLocale();
  const normalizedQuery = query.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(normalizedQuery);
  const [open, setOpen] = useState(false);
  const selectionOwner = hashKey([normalizedQuery, entityTypes]);
  const [selection, setSelection] = useState<{ owner: string; index: number } | null>(null);
  const activeIndex = selection?.owner === selectionOwner ? selection.index : -1;
  const inputRef = useRef<HTMLInputElement>(null);
  useSearchShortcut(inputRef);
  const groupRef = useRef<HTMLDivElement>(null);
  const dismissOnBlur = useFocusDismissal({
    open,
    rootRef: groupRef,
    onDismiss: () => {
      setOpen(false);
      setSelection(null);
    },
  });
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const listId = `entity-suggestions-${useId().replaceAll(":", "")}`;
  const queryReady = normalizedQuery.length >= 2 && normalizedQuery === debouncedQuery;
  const expanded = open && normalizedQuery.length >= 2;
  useImperativeHandle(
    controlRef,
    () => ({
      close: () => {
        setOpen(false);
        setSelection(null);
      },
    }),
    [],
  );
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(normalizedQuery), 250);
    return () => window.clearTimeout(timer);
  }, [normalizedQuery]);
  const result = useQuery({
    queryKey: intelligenceKeys.suggestions(debouncedQuery, entityTypes),
    queryFn: ({ signal }) => suggestEntities(debouncedQuery, entityTypes, signal),
    enabled: expanded && queryReady,
    staleTime: 30_000,
    retry: false,
  });
  const pending = !queryReady || result.isPending || result.isFetching;
  const options = queryReady && !pending && !result.isError ? (result.data ?? []) : [];
  const active = expanded ? options[activeIndex] : undefined;
  useEffect(() => {
    if (active) optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [active, activeIndex]);
  function setActiveIndex(next: number | ((current: number) => number)) {
    setSelection((current) => ({
      owner: selectionOwner,
      index: typeof next === "function" ? next(current?.owner === selectionOwner ? current.index : -1) : next,
    }));
  }
  function select(value: string) {
    if (!options.includes(value)) return;
    setOpen(false);
    setSelection(null);
    onQueryChange(value);
    onSearch(value);
  }
  function handleKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape" && expanded) {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      setSelection(null);
      return;
    }
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && options.length) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((index) =>
        event.key === "ArrowDown" ? (index + 1) % options.length : index <= 0 ? options.length - 1 : index - 1,
      );
      return;
    }
    if ((event.key === "Home" || event.key === "End") && activeIndex >= 0 && options.length) {
      event.preventDefault();
      setActiveIndex(event.key === "Home" ? 0 : options.length - 1);
      return;
    }
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (active) select(active);
    else {
      setOpen(false);
      onSearch(normalizedQuery);
    }
  }
  return (
    <div className="query-combobox" ref={groupRef}>
      <Search size={18} aria-hidden="true" />
      <input
        ref={inputRef}
        id="intelligence-query"
        value={query}
        maxLength={500}
        onChange={(event) => {
          onQueryChange(event.target.value);
          setOpen(true);
          setSelection(null);
        }}
        onKeyDown={handleKey}
        onFocus={() => setOpen(true)}
        onBlur={dismissOnBlur}
        placeholder={
          entityTypes.length === 0
            ? t("输入药物、靶点、机构或外部标识")
            : t("输入{domain}名称、别名或外部标识", { domain: domainLabel })
        }
        aria-label={t("情报检索词")}
        aria-keyshortcuts="/"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={expanded ? listId : undefined}
        aria-activedescendant={active ? `${listId}-option-${activeIndex}` : undefined}
      />
      <span className="search-shortcut" aria-hidden="true">
        <kbd>/</kbd>
      </span>
      {expanded ? (
        <div className="query-suggestions">
          {pending ? (
            <span className="suggestion-status" role="status">
              {t("正在查找相关结果")}
            </span>
          ) : null}
          {queryReady && !pending && result.isError ? (
            <span className="suggestion-status error" role="status">
              {t("联想暂不可用，可直接检索")}
              <button
                type="button"
                onClick={() => {
                  inputRef.current?.focus();
                  void result.refetch();
                }}
              >
                {t("重试联想")}
              </button>
            </span>
          ) : null}
          <div id={listId} role="listbox" aria-label={t("名称检索联想")}>
            {options.map((option, index) => (
              <button
                ref={(element) => {
                  optionRefs.current[index] = element;
                }}
                id={`${listId}-option-${index}`}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                role="option"
                aria-selected={index === activeIndex}
                key={option}
                onClick={() => select(option)}
              >
                <Search size={14} aria-hidden="true" />
                <span>{option}</span>
                <small>{domainLabel}</small>
              </button>
            ))}
          </div>
          {!pending && !result.isError && !options.length ? (
            <span className="suggestion-status" role="status">
              {t("未找到相关名称")}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
