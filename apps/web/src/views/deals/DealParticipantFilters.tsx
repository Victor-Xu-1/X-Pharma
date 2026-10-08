import { type KeyboardEvent, useRef, useState } from "react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { DealSearchFilters } from "../../lib/contracts/deals";
import { directionLabels, partyRoleLabels } from "../../lib/dealDisplay";
import type { EntityRead } from "../../lib/generated";
import { participantFilterCount } from "./dealFilterGroups";

export function DealParticipantFilters({
  filters,
  facets,
  suggestions,
  suggestionsEnabled,
  loading,
  onChange,
  onPartyText,
  onChooseParty,
}: {
  filters: DealSearchFilters;
  facets: Record<string, Record<string, number>> | undefined;
  suggestions: readonly EntityRead[];
  suggestionsEnabled: boolean;
  loading: boolean;
  onChange: <K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) => void;
  onPartyText: (value: string) => void;
  onChooseParty: (entityId: string, name: string) => void;
}) {
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const visibleSuggestions = suggestionsEnabled && suggestionsOpen;

  function handleSuggestionKey(event: KeyboardEvent<HTMLElement>) {
    if (!visibleSuggestions || event.nativeEvent.isComposing) return;
    if (event.key === "Escape" && !event.repeat) {
      event.preventDefault();
      event.stopPropagation();
      inputRef.current?.focus();
      setSuggestionsOpen(false);
      return;
    }
    if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
    const options = Array.from(suggestionsRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
    if (!options.length) return;
    event.preventDefault();
    const current = options.indexOf(event.currentTarget as HTMLButtonElement);
    const next =
      current < 0
        ? event.key === "ArrowDown"
          ? 0
          : options.length - 1
        : (current + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
    options[next]?.focus();
  }

  function chooseParty(entity: EntityRead) {
    inputRef.current?.focus();
    setSuggestionsOpen(false);
    onChooseParty(entity.id, entity.name);
  }

  return (
    <SecondaryFilters label="参与方与关联条件" activeCount={participantFilterCount(filters)}>
      <label>
        <span>交易方向</span>
        <select
          aria-label="交易方向"
          value={filters.direction}
          onChange={(event) => onChange("direction", event.target.value)}
        >
          <option value="">全部</option>
          {Object.keys(directionLabels).map((value) => (
            <option value={value} key={value}>
              {directionLabels[value]} ({facets?.direction?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <EntityFilterSelect
        label="关联适应症"
        entityType="disease"
        value={filters.diseaseEntityId}
        onChange={(entityId) => onChange("diseaseEntityId", entityId)}
        placeholder="输入适应症名称或别名"
      />
      <label
        className="deal-party-field"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setSuggestionsOpen(false);
        }}
      >
        <span>参与机构</span>
        <input
          ref={inputRef}
          role="combobox"
          aria-label="参与机构"
          aria-autocomplete="list"
          aria-expanded={visibleSuggestions}
          aria-controls={visibleSuggestions ? "deal-party-suggestions" : undefined}
          value={filters.party}
          onFocus={() => setSuggestionsOpen(true)}
          onClick={() => setSuggestionsOpen(true)}
          onKeyDown={handleSuggestionKey}
          onChange={(event) => {
            setSuggestionsOpen(true);
            onPartyText(event.target.value);
          }}
          placeholder="至少输入 2 个字符"
          maxLength={500}
        />
        {visibleSuggestions ? (
          <div
            ref={suggestionsRef}
            className="query-suggestions deal-party-suggestions"
            id="deal-party-suggestions"
            role="listbox"
            aria-label="参与机构候选"
          >
            {loading ? <span className="suggestion-status">正在查找机构</span> : null}
            {suggestions.slice(0, 8).map((entity) => {
              const identifiers = Object.values(entity.external_ids ?? {})
                .filter(Boolean)
                .slice(0, 2)
                .join(" · ");
              return (
                <button
                  type="button"
                  role="option"
                  aria-label={identifiers ? `${entity.name} · ${identifiers}` : entity.name}
                  key={entity.id}
                  onKeyDown={handleSuggestionKey}
                  onClick={() => chooseParty(entity)}
                >
                  <span>{entity.name}</span>
                  {identifiers ? <small>{identifiers}</small> : null}
                </button>
              );
            })}
            {!loading && suggestions.length === 0 ? <span className="suggestion-status">未找到匹配机构</span> : null}
          </div>
        ) : null}
      </label>
      <label>
        <span>参与角色</span>
        <select
          aria-label="参与角色"
          value={filters.partyRole}
          onChange={(event) => onChange("partyRole", event.target.value)}
        >
          <option value="">全部</option>
          {Object.keys(partyRoleLabels).map((value) => (
            <option value={value} key={value}>
              {partyRoleLabels[value]} ({facets?.party_role?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
    </SecondaryFilters>
  );
}
