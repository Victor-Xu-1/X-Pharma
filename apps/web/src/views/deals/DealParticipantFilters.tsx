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
      <label className="deal-party-field">
        <span>参与机构</span>
        <input
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={suggestionsEnabled && suggestions.length > 0}
          aria-controls="deal-party-suggestions"
          value={filters.party}
          onChange={(event) => onPartyText(event.target.value)}
          placeholder="至少输入 2 个字符"
          maxLength={500}
        />
        {suggestionsEnabled ? (
          <div className="query-suggestions deal-party-suggestions" id="deal-party-suggestions" role="listbox">
            {loading ? <span className="suggestion-status">正在查找机构</span> : null}
            {suggestions.slice(0, 8).map((entity) => (
              <button type="button" role="option" key={entity.id} onClick={() => onChooseParty(entity.id, entity.name)}>
                <span>{entity.name}</span>
                <small>
                  {entity.external_ids ? Object.values(entity.external_ids).slice(0, 2).join(" · ") : "机构"}
                </small>
              </button>
            ))}
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
