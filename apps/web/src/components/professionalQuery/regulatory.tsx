import { RefreshCw, SlidersHorizontal } from "lucide-react";
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
  return (
    <>
      {regulatoryCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          正在读取监管筛选选项
        </div>
      ) : null}
      {regulatoryCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>监管筛选选项暂不可用</span>
          <button type="button" className="text-button" onClick={() => void regulatoryCatalog.refetch()}>
            <RefreshCw size={13} />
            重试
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label="监管机构"
        options={regulatoryAgencyOptions}
        value={draft.regulatoryAgency}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryAgency", value)}
      />
      <GovernedFacetSelect
        label="辖区"
        options={regulatoryJurisdictionOptions}
        value={draft.regulatoryJurisdiction}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryJurisdiction", value)}
      />
      <GovernedFacetSelect
        label="事件类型"
        options={regulatoryEventTypeOptions}
        value={draft.regulatoryEventType}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryEventType", value)}
      />
      <GovernedFacetSelect
        label="事件状态"
        options={regulatoryStatusOptions}
        value={draft.regulatoryStatus}
        state={regulatoryCatalogState}
        onChange={(value) => update("regulatoryStatus", value)}
      />
      <DateRange
        label="监管决定日期"
        from={draft.regulatoryDecisionFrom}
        to={draft.regulatoryDecisionTo}
        onChange={(from, to) => updateDateRange("regulatoryDecisionFrom", "regulatoryDecisionTo", from, to)}
      />
      <details className="professional-more-fields" open={regulatoryAdvancedConditionCount > 0 || undefined}>
        <summary>
          <SlidersHorizontal size={14} />
          <span>更多监管与安全条件</span>
          <small>
            {regulatoryAdvancedConditionCount
              ? `已选 ${regulatoryAdvancedConditionCount} 项`
              : "认定、标签、安全与来源时间"}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <GovernedFacetSelect
            label="认定资格"
            options={regulatoryDesignationOptions}
            value={draft.regulatoryDesignationType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryDesignationType", value)}
          />
          <GovernedFacetSelect
            label="标签变更"
            options={regulatoryLabelChangeOptions}
            value={draft.regulatoryLabelChangeType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryLabelChangeType", value)}
          />
          <GovernedFacetSelect
            label="黑框警告"
            options={regulatoryBoxedWarningOptions}
            value={draft.regulatoryBoxedWarning}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatoryBoxedWarning", value as "" | "true" | "false")}
          />
          <GovernedFacetSelect
            label="安全信号"
            options={regulatorySafetySignalOptions}
            value={draft.regulatorySafetySignalType}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetySignalType", value)}
          />
          <GovernedFacetSelect
            label="严重程度"
            options={regulatorySafetySeverityOptions}
            value={draft.regulatorySafetySeverity}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetySeverity", value)}
          />
          <GovernedFacetSelect
            label="信号状态"
            options={regulatorySafetyStatusOptions}
            value={draft.regulatorySafetyStatus}
            state={regulatoryCatalogState}
            onChange={(value) => update("regulatorySafetyStatus", value)}
          />
          <DateRange
            label="来源更新日期"
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
