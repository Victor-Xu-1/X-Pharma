import { Search } from "lucide-react";
import { EntityMultiFilterSelect } from "../../components/EntityMultiFilterSelect";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { localizedTrialPhase, localizedTrialStatus } from "../../lib/i18n/trialVocabulary";
import { trialFilterOptions } from "./filterOptions";
import type { TrialFilterProps } from "./filterTypes";
export function TrialPrimaryFilters({ filters, setters, data, rememberRoleEntity }: TrialFilterProps) {
  const { query, status, phase, investigationalDrugEntityIds, investigationalTargetEntityIds } = filters;
  const {
    setQuery,
    setStatus,
    setPhase,
    setInvestigationalDrugEntityIds,
    setInvestigationalTargetEntityIds,
    setRoleEntityId,
    setRoleEntityIds,
    setRoleEntityRole,
  } = setters;
  const { statuses, phases } = trialFilterOptions(data, filters);
  return (
    <>
      <label className="domain-query-field">
        <span>{t("关键词")}</span>
        <span className="input-with-icon">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("注册号、标题、疾病、干预、申办方或关联实体")}
            maxLength={500}
          />
        </span>
      </label>
      <label>
        <span>{t("招募状态")}</span>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{t("全部")}</option>
          {statuses.map((value) => (
            <option value={value} key={value}>
              {localizedTrialStatus(value)} ({data?.facets?.overall_status?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("临床分期")}</span>
        <select value={phase} onChange={(event) => setPhase(event.target.value)}>
          <option value="">{t("全部")}</option>
          {phases.map((value) => (
            <option value={value} key={value}>
              {localizedTrialPhase(value)} ({data?.facets?.phase?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <EntityMultiFilterSelect
        label={t("试验药物（任一）")}
        entityType="drug"
        values={investigationalDrugEntityIds}
        placeholder={t("输入至少 2 个字符添加试验药物")}
        onResolved={rememberRoleEntity}
        onChange={(entityIds, selectedId, displayName) => {
          setInvestigationalDrugEntityIds(entityIds);
          setRoleEntityId("");
          setRoleEntityIds([]);
          setRoleEntityRole("");
          if (selectedId) rememberRoleEntity(selectedId, displayName);
        }}
      />
      <EntityMultiFilterSelect
        label={t("试验靶点（任一）")}
        entityType="target"
        values={investigationalTargetEntityIds}
        placeholder={t("输入至少 2 个字符添加试验靶点")}
        onResolved={rememberRoleEntity}
        onChange={(entityIds, selectedId, displayName) => {
          setInvestigationalTargetEntityIds(entityIds);
          setRoleEntityId("");
          setRoleEntityIds([]);
          setRoleEntityRole("");
          if (selectedId) rememberRoleEntity(selectedId, displayName);
        }}
      />
    </>
  );
}
