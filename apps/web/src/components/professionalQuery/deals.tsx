import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { useMessages } from "../../lib/i18n";
import { professionalQueryMessages } from "../../lib/i18n/professionalQuery";
import { EntityFilterSelect } from "../EntityFilterSelect";
import { DateRange, GovernedFacetField, GovernedFacetSelect } from "./fields";
import type { ProfessionalQueryModel } from "./useProfessionalQueryModel";

type Props = Pick<
  ProfessionalQueryModel,
  | "dealCatalog"
  | "dealCatalogState"
  | "dealTypeOptions"
  | "dealStatusOptions"
  | "dealDirectionOptions"
  | "dealTerritoryOptions"
  | "dealAssetModalityOptions"
  | "dealAssetProgramTagOptions"
  | "dealPartyRoleOptions"
  | "dealPartyCountryOptions"
  | "dealPartyOrganizationTypeOptions"
  | "dealTransactionPhaseOptions"
  | "dealCurrentPhaseOptions"
  | "dealRightTypeOptions"
  | "dealRightsTerritoryOptions"
  | "dealCurrencyOptions"
  | "dealAdvancedConditionCount"
  | "draft"
  | "update"
  | "updateDateRange"
>;

export function DealsFields({
  dealCatalog,
  dealCatalogState,
  dealTypeOptions,
  dealStatusOptions,
  dealDirectionOptions,
  dealTerritoryOptions,
  dealAssetModalityOptions,
  dealAssetProgramTagOptions,
  dealPartyRoleOptions,
  dealPartyCountryOptions,
  dealPartyOrganizationTypeOptions,
  dealTransactionPhaseOptions,
  dealCurrentPhaseOptions,
  dealRightTypeOptions,
  dealRightsTerritoryOptions,
  dealCurrencyOptions,
  dealAdvancedConditionCount,
  draft,
  update,
  updateDateRange,
}: Props) {
  const t = useMessages(professionalQueryMessages);
  return (
    <>
      <div className="professional-entity-row">
        <EntityFilterSelect
          label={t("交易药品")}
          entityType="drug"
          value={draft.dealAssetEntityId}
          onChange={(value) => update("dealAssetEntityId", value)}
          placeholder={t("输入规范药品")}
        />
        <EntityFilterSelect
          label={t("关联靶点")}
          entityType="target"
          value={draft.dealTargetEntityId}
          onChange={(value) => update("dealTargetEntityId", value)}
          placeholder={t("输入规范靶点")}
        />
        <EntityFilterSelect
          label={t("关联适应症")}
          entityType="disease"
          value={draft.dealDiseaseEntityId}
          onChange={(value) => update("dealDiseaseEntityId", value)}
          placeholder={t("输入疾病或适应症")}
        />
        <EntityFilterSelect
          label={t("参与机构")}
          entityType="organization"
          value={draft.dealPartyEntityId}
          onChange={(value) => update("dealPartyEntityId", value)}
          placeholder={t("输入规范机构")}
        />
      </div>
      {dealCatalog.isPending ? (
        <div className="professional-facet-catalog-state" role="status">
          {t("正在读取交易筛选选项")}
        </div>
      ) : null}
      {dealCatalog.isError ? (
        <div className="professional-facet-catalog-state error" role="alert">
          <span>{t("交易筛选选项暂不可用")}</span>
          <button type="button" className="text-button" onClick={() => void dealCatalog.refetch()}>
            <RefreshCw size={13} />
            {t("重试")}
          </button>
        </div>
      ) : null}
      <GovernedFacetSelect
        label={t("交易类型")}
        options={dealTypeOptions}
        value={draft.dealType}
        state={dealCatalogState}
        onChange={(value) => update("dealType", value)}
      />
      <GovernedFacetSelect
        label={t("交易状态")}
        options={dealStatusOptions}
        value={draft.dealStatus}
        state={dealCatalogState}
        onChange={(value) => update("dealStatus", value)}
      />
      <GovernedFacetSelect
        label={t("交易方向")}
        options={dealDirectionOptions}
        value={draft.dealDirection}
        state={dealCatalogState}
        onChange={(value) => update("dealDirection", value)}
      />
      <DateRange
        label={t("交易披露日期")}
        from={draft.dealAnnouncedFrom}
        to={draft.dealAnnouncedTo}
        onChange={(from, to) => updateDateRange("dealAnnouncedFrom", "dealAnnouncedTo", from, to)}
      />
      <details className="professional-more-fields" open={dealAdvancedConditionCount > 0 || undefined}>
        <summary>
          <SlidersHorizontal size={14} />
          <span>{t("更多交易条件")}</span>
          <small>
            {dealAdvancedConditionCount
              ? t("已选 {count} 项", { count: dealAdvancedConditionCount })
              : t("资产、参与方、权益与金额")}
          </small>
        </summary>
        <div className="professional-more-fields-grid">
          <label>
            <span>{t("方向参照地区")}</span>
            <input
              value={draft.dealDirectionReferenceJurisdiction}
              onChange={(event) => update("dealDirectionReferenceJurisdiction", event.target.value)}
              placeholder={t("如 CN、US")}
              maxLength={128}
            />
          </label>
          <GovernedFacetSelect
            label={t("交易地域")}
            options={dealTerritoryOptions}
            value={draft.dealTerritory}
            state={dealCatalogState}
            onChange={(value) => update("dealTerritory", value)}
          />
          <GovernedFacetField
            label={t("资产模态")}
            options={dealAssetModalityOptions}
            selected={draft.dealAssetModalities}
            state={dealCatalogState}
            onChange={(values) => update("dealAssetModalities", values)}
          />
          <GovernedFacetField
            label={t("资产项目标签")}
            options={dealAssetProgramTagOptions}
            selected={draft.dealAssetProgramTags}
            state={dealCatalogState}
            onChange={(values) => update("dealAssetProgramTags", values)}
          />
          <GovernedFacetSelect
            label={t("参与角色")}
            options={dealPartyRoleOptions}
            value={draft.dealPartyRole}
            state={dealCatalogState}
            onChange={(value) => update("dealPartyRole", value)}
          />
          <GovernedFacetSelect
            label={t("机构所在地区")}
            options={dealPartyCountryOptions}
            value={draft.dealPartyCountryRegion}
            state={dealCatalogState}
            onChange={(value) => update("dealPartyCountryRegion", value)}
          />
          <GovernedFacetSelect
            label={t("机构类型")}
            options={dealPartyOrganizationTypeOptions}
            value={draft.dealPartyOrganizationType}
            state={dealCatalogState}
            onChange={(value) => update("dealPartyOrganizationType", value)}
          />
          <GovernedFacetSelect
            label={t("交易时阶段")}
            options={dealTransactionPhaseOptions}
            value={draft.dealDevelopmentPhaseAtTransaction}
            state={dealCatalogState}
            onChange={(value) => update("dealDevelopmentPhaseAtTransaction", value)}
          />
          <GovernedFacetSelect
            label={t("当前最高阶段")}
            options={dealCurrentPhaseOptions}
            value={draft.dealCurrentDevelopmentPhase}
            state={dealCatalogState}
            onChange={(value) => update("dealCurrentDevelopmentPhase", value)}
          />
          <GovernedFacetSelect
            label={t("权益类型")}
            options={dealRightTypeOptions}
            value={draft.dealRightType}
            state={dealCatalogState}
            onChange={(value) => update("dealRightType", value)}
          />
          <GovernedFacetSelect
            label={t("权益地区")}
            options={dealRightsTerritoryOptions}
            value={draft.dealRightsTerritory}
            state={dealCatalogState}
            onChange={(value) => update("dealRightsTerritory", value)}
          />
          <GovernedFacetSelect
            label={t("币种")}
            options={dealCurrencyOptions}
            value={draft.dealCurrency}
            state={dealCatalogState}
            onChange={(value) => update("dealCurrency", value)}
          />
          <DateRange
            label={t("终止日期")}
            from={draft.dealTerminatedFrom}
            to={draft.dealTerminatedTo}
            onChange={(from, to) => updateDateRange("dealTerminatedFrom", "dealTerminatedTo", from, to)}
          />
          <DateRange
            label={t("信息更新日期")}
            from={draft.dealSourceUpdatedFrom}
            to={draft.dealSourceUpdatedTo}
            onChange={(from, to) => updateDateRange("dealSourceUpdatedFrom", "dealSourceUpdatedTo", from, to)}
          />
          <label>
            <span>{t("首付款下限")}</span>
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={draft.dealUpfrontAmountMin}
              onChange={(event) => update("dealUpfrontAmountMin", event.target.value)}
              placeholder={t("例如 10000000")}
            />
          </label>
          <label>
            <span>{t("首付款上限")}</span>
            <input
              type="number"
              min={draft.dealUpfrontAmountMin || "0"}
              step="0.01"
              inputMode="decimal"
              value={draft.dealUpfrontAmountMax}
              onChange={(event) => update("dealUpfrontAmountMax", event.target.value)}
              placeholder={t("例如 30000000")}
            />
          </label>
          <label>
            <span>{t("潜在总额下限")}</span>
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={draft.dealTotalPotentialAmountMin}
              onChange={(event) => update("dealTotalPotentialAmountMin", event.target.value)}
              placeholder={t("例如 100000000")}
            />
          </label>
          <label>
            <span>{t("潜在总额上限")}</span>
            <input
              type="number"
              min={draft.dealTotalPotentialAmountMin || "0"}
              step="0.01"
              inputMode="decimal"
              value={draft.dealTotalPotentialAmountMax}
              onChange={(event) => update("dealTotalPotentialAmountMax", event.target.value)}
              placeholder={t("例如 500000000")}
            />
          </label>
        </div>
      </details>
    </>
  );
}
