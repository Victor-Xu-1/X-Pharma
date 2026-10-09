import { formatDate } from "../../components/common";
import type {
  EpidemiologyFilters,
  EpidemiologyObservation,
  EpidemiologyTrendResult,
} from "../../lib/contracts/epidemiology";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../../lib/epidemiologyDisplay";
import { formattingLocale } from "../../lib/i18n";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";

export type TrendSelection = {
  observationId: string;
  diseaseId: string;
  diseaseName: string;
  filters: EpidemiologyFilters;
};
export function measureValue(value: string): string {
  return Object.hasOwn(epidemiologyMeasureLabels, value)
    ? professionalEnumLabel(epidemiologyMeasureLabels[value], value)
    : value;
}
export function sexValue(value: string | null): string {
  if (value === null) return t("未标注");
  return Object.hasOwn(epidemiologySexLabels, value)
    ? professionalEnumLabel(epidemiologySexLabels[value], value)
    : value;
}
export function formatNumber(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat(formattingLocale(), { maximumSignificantDigits: 21 }).format(value);
}
export function estimateLabel(item: EpidemiologyObservation): string {
  const interval =
    item.lower_bound !== null || item.upper_bound !== null
      ? ` (${formatNumber(item.lower_bound)}-${formatNumber(item.upper_bound)})`
      : "";
  return `${formatNumber(item.value)}${interval}`;
}
export function periodLabel(item: EpidemiologyObservation): string {
  if (!item.period_start && !item.period_end) return t("未标注");
  if (item.period_start === item.period_end) return formatDate(item.period_start ?? "");
  return `${formatDate(item.period_start ?? "")} - ${formatDate(item.period_end ?? "")}`;
}
export function comparableTrend(item: EpidemiologyObservation): TrendSelection {
  return {
    observationId: item.id,
    diseaseId: item.disease_entity.id,
    diseaseName: item.disease_entity.name,
    filters: {
      query: "",
      displayMode: "list",
      analysisView: "chart",
      diseaseEntityId: item.disease_entity.id,
      measure: item.measure,
      geography: item.geography,
      unit: item.unit,
      patientPopulationId: item.patient_population_id ?? "",
      populationScope: item.population_scope,
      ageGroup: item.age_group ?? "",
      sex: item.sex ?? "",
      periodStartFrom: "",
      periodEndTo: "",
      sortBy: "period_end",
      sortDirection: "desc",
    },
  };
}
export function trendMatchesSelection(data: EpidemiologyTrendResult, selection: TrendSelection): boolean {
  const filters = selection.filters;
  return (
    data.disease.id === selection.diseaseId &&
    data.items.every(
      (item) =>
        item.disease_entity.id === selection.diseaseId &&
        item.measure === filters.measure &&
        item.geography === filters.geography &&
        item.unit === filters.unit &&
        (item.patient_population_id ?? "") === filters.patientPopulationId &&
        item.population_scope === filters.populationScope &&
        (item.age_group ?? "") === filters.ageGroup &&
        (item.sex ?? "") === filters.sex,
    )
  );
}
