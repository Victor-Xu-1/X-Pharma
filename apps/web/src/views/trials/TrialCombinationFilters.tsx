import { EntityMultiFilterSelect } from "../../components/EntityMultiFilterSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import { clinicalText as t } from "../../lib/i18n/clinical";
import type { TrialFilterProps } from "./filterTypes";
export function TrialCombinationFilters({ filters, setters, rememberRoleEntity }: TrialFilterProps) {
  const { combinationDrugEntityIds, combinationTargetEntityIds } = filters;
  const {
    setCombinationDrugEntityIds,
    setCombinationTargetEntityIds,
    setRoleEntityId,
    setRoleEntityIds,
    setRoleEntityRole,
  } = setters;

  return (
    <SecondaryFilters
      label={t("联用药物与靶点")}
      activeCount={[combinationDrugEntityIds.length, combinationTargetEntityIds.length].filter(Boolean).length}
    >
      <EntityMultiFilterSelect
        label={t("联用药物（任一）")}
        entityType="drug"
        values={combinationDrugEntityIds}
        placeholder={t("输入至少 2 个字符添加联用药物")}
        onResolved={rememberRoleEntity}
        onChange={(entityIds, selectedId, displayName) => {
          setCombinationDrugEntityIds(entityIds);
          setRoleEntityId("");
          setRoleEntityIds([]);
          setRoleEntityRole("");
          if (selectedId) rememberRoleEntity(selectedId, displayName);
        }}
      />
      <EntityMultiFilterSelect
        label={t("联用靶点（任一）")}
        entityType="target"
        values={combinationTargetEntityIds}
        placeholder={t("输入至少 2 个字符添加联用靶点")}
        onResolved={rememberRoleEntity}
        onChange={(entityIds, selectedId, displayName) => {
          setCombinationTargetEntityIds(entityIds);
          setRoleEntityId("");
          setRoleEntityIds([]);
          setRoleEntityRole("");
          if (selectedId) rememberRoleEntity(selectedId, displayName);
        }}
      />
    </SecondaryFilters>
  );
}
