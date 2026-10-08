import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import { DateRange, GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "regulatoryCatalog"
  | "regulatoryCatalogState"
  | "regulatoryAgencyOptions"
  | "regulatoryJurisdictionOptions"
  | "regulatoryEventTypeOptions"
  | "regulatoryStatusOptions"
  | "regulatoryDesignationOptions"
  | "regulatoryLabelChangeOptions"
  | "regulatoryBoxedWarningOptions"
  | "regulatorySafetySignalOptions"
  | "regulatorySafetySeverityOptions"
  | "regulatorySafetyStatusOptions"
  | "regulatoryAdvancedConditionCount"
  | "draft"
  | "update"
  | "updateDateRange"
>;

export function RegulatoryFields({
  regulatoryCatalog,
  regulatoryCatalogState,
  regulatoryAgencyOptions,
  regulatoryJurisdictionOptions,
  regulatoryEventTypeOptions,
  regulatoryStatusOptions,
  regulatoryDesignationOptions,
  regulatoryLabelChangeOptions,
  regulatoryBoxedWarningOptions,
  regulatorySafetySignalOptions,
  regulatorySafetySeverityOptions,
  regulatorySafetyStatusOptions,
  regulatoryAdvancedConditionCount,
  draft,
  update,
  updateDateRange,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      {regulatoryCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          {t("正在读取监管筛选选项")}
        </div>
      ) : null}
      {regulatoryCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>{t("监管筛选选项暂不可用")}</span>
          <button type="button" className="text-button" onClick={() => void regulatoryCatalog.refetch()}>
            <RefreshCw size={13} />
            {t("重试")}
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label={t("监管机构")}
        options={regulatoryAgencyOptions}
        value={draft.regulatoryAgency}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryAgency", value)}
      />
      <GovernedFacetSelect
        label={t("辖区")}
        options={regulatoryJurisdictionOptions}
        value={draft.regulatoryJurisdiction}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryJurisdiction", value)}
      />
      <GovernedFacetSelect
        label={t("事件类型")}
        options={regulatoryEventTypeOptions}
        value={draft.regulatoryEventType}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryEventType", value)}
      />
      <GovernedFacetSelect
        label={t("事件状态")}
        options={regulatoryStatusOptions}
        value={draft.regulatoryStatus}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryStatus", value)}
      />
      <DateRange
        label={t("监管决定日期")}
        from={draft.regulatoryDecisionFrom}
        to={draft.regulatoryDecisionTo}
        onChange={(from, to) => updateDateRange("regulatoryDecisionFrom", "regulatoryDecisionTo", from, to)}
      />
      <details className="professional-more-fields" open={regulatoryAdvancedConditionCount > 0 || undefined}>
        <summary>
          <SlidersHorizontal size={14} />
          <span>{t("更多监管与安全条件")}</span>
          <small>
            {regulatoryAdvancedConditionCount
              ? t("已选 {count} 项", { count: regulatoryAdvancedConditionCount })
              : t("认定、标签、安全与来源时间")}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <GovernedFacetSelect
            label={t("认定资格")}
            options={regulatoryDesignationOptions}
            value={draft.regulatoryDesignationType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryDesignationType", value)}
          />
          <GovernedFacetSelect
            label={t("标签变更")}
            options={regulatoryLabelChangeOptions}
            value={draft.regulatoryLabelChangeType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryLabelChangeType", value)}
          />
          <GovernedFacetSelect
            label={t("黑框警告")}
            options={regulatoryBoxedWarningOptions}
            value={draft.regulatoryBoxedWarning}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryBoxedWarning", value as "" | "true" | "false")}
          />
          <GovernedFacetSelect
            label={t("安全信号")}
            options={regulatorySafetySignalOptions}
            value={draft.regulatorySafetySignalType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetySignalType", value)}
          />
          <GovernedFacetSelect
            label={t("严重程度")}
            options={regulatorySafetySeverityOptions}
            value={draft.regulatorySafetySeverity}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetySeverity", value)}
          />
          <GovernedFacetSelect
            label={t("信号状态")}
            options={regulatorySafetyStatusOptions}
            value={draft.regulatorySafetyStatus}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetyStatus", value)}
          />
          <DateRange
            label={t("来源更新日期")}
            from={draft.regulatorySourceUpdatedFrom}
            to={draft.regulatorySourceUpdatedTo}
            onChange={(from, to) =>
              updateDateRange("regulatorySourceUpdatedFrom", "regulatorySourceUpdatedTo", from, to)
            }
          />
        </div>
      </details>
    </>
  );
}
