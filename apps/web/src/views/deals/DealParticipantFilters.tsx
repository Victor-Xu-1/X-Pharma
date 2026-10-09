import { type KeyboardEvent, useRef, useState } from "react";
import { EntityFilterSelect } from "../../components/EntityFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { DealSearchFilters } from "../../lib/contracts/deals";
import { dealLabel, directionLabels, partyRoleLabels } from "../../lib/dealDisplay";
import type { EntityRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { participantFilterCount } from "./dealFilterGroups";

export function DealParticipantFilters({
  filters,
  facets,
  suggestions,
  suggestionsEnabled,
  loading,
  error,
  onRetry,
  onChange,
  onPartyText,
  onChooseParty,
}: {
  filters: DealSearchFilters;
  facets: Record<string, Record<string, number>> | undefined;
  suggestions: readonly EntityRead[];
  suggestionsEnabled: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onChange: <K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) => void;
  onPartyText: (value: string) => void;
  onChooseParty: (entityId: string, name: string) => void;
}) {
  useLocale();
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
    <SecondaryFilters label={t("参与方与关联条件")} activeCount={participantFilterCount(filters)}>
      <EntityFilterSelect
        label={t("交易药品")}
        entityType="drug"
        value={filters.assetEntityId}
        onChange={(entityId) => onChange("assetEntityId", entityId)}
        placeholder={t("输入药品名称或别名")}
      />
      <EntityFilterSelect
        label={t("关联靶点")}
        entityType="target"
        value={filters.targetEntityId}
        onChange={(entityId) => onChange("targetEntityId", entityId)}
        placeholder={t("输入靶点名称或别名")}
      />

      <label>
        <span>{t("交易方向")}</span>
        <select
          aria-label={t("交易方向")}
          value={filters.direction}
          onChange={(event) => onChange("direction", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.keys(directionLabels).map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, directionLabels)} ({facets?.direction?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <EntityFilterSelect
        label={t("关联适应症")}
        entityType="disease"
        value={filters.diseaseEntityId}
        onChange={(entityId) => onChange("diseaseEntityId", entityId)}
        placeholder={t("输入适应症名称或别名")}
      />
      <fieldset
        className="deal-party-field"
        aria-label={t("参与机构候选")}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setSuggestionsOpen(false);
        }}
      >
        <label>
          <span>{t("参与机构")}</span>
          <input
            ref={inputRef}
            role="combobox"
            aria-label={t("参与机构")}
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
            placeholder={t("至少输入 2 个字符")}
            maxLength={500}
          />
        </label>
        {visibleSuggestions ? (
          <div className="query-suggestions deal-party-suggestions" id="deal-party-suggestions">
            {loading ? (
              <span className="suggestion-status" role="status">
                {t("正在查找机构")}
              </span>
            ) : null}
            {!loading && error !== null ? (
              <div className="suggestion-status">
                <p role="alert">{t("机构查询失败：{reason}", { reason: error })}</p>
                <button type="button" onClick={onRetry}>
                  {t("重试机构查询")}
                </button>
              </div>
            ) : null}
            {!loading && error === null && suggestions.length > 0 ? (
              <div ref={suggestionsRef} role="listbox" aria-label={t("参与机构候选")}>
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
              </div>
            ) : null}
            {!loading && error === null && suggestions.length === 0 ? (
              <span className="suggestion-status" role="status">
                {t("未找到匹配机构")}
              </span>
            ) : null}
          </div>
        ) : null}
      </fieldset>
      <label>
        <span>{t("参与角色")}</span>
        <select
          aria-label={t("参与角色")}
          value={filters.partyRole}
          onChange={(event) => onChange("partyRole", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {Object.keys(partyRoleLabels).map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, partyRoleLabels)} ({facets?.party_role?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
    </SecondaryFilters>
  );
}
