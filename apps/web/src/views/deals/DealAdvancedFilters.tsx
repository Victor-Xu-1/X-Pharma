import { FacetMultiSelect } from "../../components/FacetMultiSelect";
import { SecondaryFilters } from "../../components/SecondaryFilters";
import type { DealSearchFilters } from "../../lib/contracts/deals";
import { dealLabel, phaseLabels, rightTypeLabels } from "../../lib/dealDisplay";
import { facetOptions } from "../../lib/facets";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { programTagLabel, publicProgramTags } from "../../lib/programDisplay";
import { AmountRangeFields, DateRangeFields } from "./DealRangeFields";
import { advancedDealFilterCount } from "./dealFilterGroups";

export function DealAdvancedFilters({
  filters,
  facets,
  updateFilter,
}: {
  filters: DealSearchFilters;
  facets: Record<string, Record<string, number>> | undefined;
  updateFilter: <K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) => void;
}) {
  useLocale();
  const territories = facetOptions(facets, "territory", filters.territory);
  const partyCountries = facetOptions(facets, "party_country_region", filters.partyCountryRegion);
  const partyOrganizationTypes = facetOptions(facets, "party_organization_type", filters.partyOrganizationType);
  const assetModalities = facetOptions(facets, "asset_modality", filters.assetModalities);
  const assetProgramTags = publicProgramTags(facetOptions(facets, "asset_program_tag", filters.assetProgramTags));
  const rightsTerritories = facetOptions(facets, "rights_territory", filters.rightsTerritory);
  const currencies = facetOptions(facets, "currency", filters.currency);
  const phaseOptions = facetOptions(facets, "development_phase_at_transaction", [
    filters.developmentPhaseAtTransaction,
    ...Object.keys(phaseLabels),
  ]);
  const currentPhaseOptions = facetOptions(facets, "current_development_phase", [
    filters.currentDevelopmentPhase,
    ...Object.keys(phaseLabels),
  ]);
  const rightTypeOptions = facetOptions(facets, "right_type", [filters.rightType, ...Object.keys(rightTypeLabels)]);
  return (
    <SecondaryFilters label={t("更多交易条件")} activeCount={advancedDealFilterCount(filters)}>
      <label>
        <span>{t("方向参照地区")}</span>
        <input
          value={filters.directionReferenceJurisdiction}
          onChange={(event) => updateFilter("directionReferenceJurisdiction", event.target.value)}
          placeholder={t("例如 US")}
          maxLength={120}
        />
      </label>
      <label>
        <span>{t("交易地域")}</span>
        <select value={filters.territory} onChange={(event) => updateFilter("territory", event.target.value)}>
          <option value="">{t("全部")}</option>
          {territories.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.territory?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("机构所在地区")}</span>
        <input
          list="deal-party-country-options"
          value={filters.partyCountryRegion}
          onChange={(event) => updateFilter("partyCountryRegion", event.target.value)}
          maxLength={120}
        />
        <datalist id="deal-party-country-options">
          {partyCountries.map((value) => (
            <option value={value} key={value} label={String(facets?.party_country_region?.[value] ?? 0)} />
          ))}
        </datalist>
      </label>
      <label>
        <span>{t("机构类型")}</span>
        <input
          list="deal-party-organization-type-options"
          value={filters.partyOrganizationType}
          onChange={(event) => updateFilter("partyOrganizationType", event.target.value)}
          maxLength={120}
        />
        <datalist id="deal-party-organization-type-options">
          {partyOrganizationTypes.map((value) => (
            <option value={value} key={value} label={String(facets?.party_organization_type?.[value] ?? 0)} />
          ))}
        </datalist>
      </label>
      <FacetMultiSelect
        label={t("资产模态")}
        options={assetModalities.map((value) => ({
          value,
          label: programTagLabel(value),
          count: facets?.asset_modality?.[value] ?? 0,
        }))}
        selected={filters.assetModalities}
        onChange={(values) => updateFilter("assetModalities", values)}
      />
      <FacetMultiSelect
        label={t("资产项目标签")}
        options={assetProgramTags.map((value) => ({
          value,
          label: value,
          count: facets?.asset_program_tag?.[value] ?? 0,
        }))}
        selected={filters.assetProgramTags}
        onChange={(values) => updateFilter("assetProgramTags", values)}
      />
      <label>
        <span>{t("交易时阶段")}</span>
        <select
          value={filters.developmentPhaseAtTransaction}
          onChange={(event) => updateFilter("developmentPhaseAtTransaction", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {phaseOptions.map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, phaseLabels)} ({facets?.development_phase_at_transaction?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("当前最高阶段")}</span>
        <select
          value={filters.currentDevelopmentPhase}
          onChange={(event) => updateFilter("currentDevelopmentPhase", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {currentPhaseOptions.map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, phaseLabels)} ({facets?.current_development_phase?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("权益类型")}</span>
        <select value={filters.rightType} onChange={(event) => updateFilter("rightType", event.target.value)}>
          <option value="">{t("全部")}</option>
          {rightTypeOptions.map((value) => (
            <option value={value} key={value}>
              {dealLabel(value, rightTypeLabels)} ({facets?.right_type?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("权益地区")}</span>
        <select
          value={filters.rightsTerritory}
          onChange={(event) => updateFilter("rightsTerritory", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {rightsTerritories.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.rights_territory?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t("币种")}</span>
        <select
          aria-label={t("币种")}
          value={filters.currency}
          onChange={(event) => updateFilter("currency", event.target.value)}
        >
          <option value="">{t("全部")}</option>
          {currencies.map((value) => (
            <option value={value} key={value}>
              {value} ({facets?.currency?.[value] ?? 0})
            </option>
          ))}
        </select>
      </label>
      <DateRangeFields
        label={t("初始披露")}
        from={filters.announcedFrom}
        to={filters.announcedTo}
        onFrom={(value) => updateFilter("announcedFrom", value)}
        onTo={(value) => updateFilter("announcedTo", value)}
      />
      <DateRangeFields
        label={t("终止日期")}
        from={filters.terminatedFrom}
        to={filters.terminatedTo}
        onFrom={(value) => updateFilter("terminatedFrom", value)}
        onTo={(value) => updateFilter("terminatedTo", value)}
      />
      <DateRangeFields
        label={t("信息更新")}
        from={filters.sourceUpdatedFrom}
        to={filters.sourceUpdatedTo}
        onFrom={(value) => updateFilter("sourceUpdatedFrom", value)}
        onTo={(value) => updateFilter("sourceUpdatedTo", value)}
      />
      <AmountRangeFields
        label={t("首付款")}
        minimum={filters.upfrontAmountMin}
        maximum={filters.upfrontAmountMax}
        onMinimum={(value) => updateFilter("upfrontAmountMin", value)}
        onMaximum={(value) => updateFilter("upfrontAmountMax", value)}
      />
      <AmountRangeFields
        label={t("潜在总额")}
        minimum={filters.totalPotentialAmountMin}
        maximum={filters.totalPotentialAmountMax}
        onMinimum={(value) => updateFilter("totalPotentialAmountMin", value)}
        onMaximum={(value) => updateFilter("totalPotentialAmountMax", value)}
      />
    </SecondaryFilters>
  );
}
