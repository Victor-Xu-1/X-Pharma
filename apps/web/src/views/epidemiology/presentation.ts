import { formatDate } from "../../components/common";
import type {
  EpidemiologyFilters,
  EpidemiologyObservation,
  EpidemiologyTrendResult,
} from "../../lib/contracts/epidemiology";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../../lib/epidemiologyDisplay";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";

export { formatScientificNumber as formatNumber } from "../../lib/scientificNumber";

import { formatScientificNumber as formatNumber } from "../../lib/scientificNumber";

export type TrendSelection = {
  observationId: string;
  diseaseId: string;
  diseaseName: string;
  publisherId: string | null;
  methodology: string | null;
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
    publisherId: item.publisher_entity_id ?? null,
    methodology: item.methodology,
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
    data.anchor_observation_id === selection.observationId &&
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
        (item.sex ?? "") === filters.sex &&
        (item.publisher_entity_id ?? null) === selection.publisherId &&
        item.methodology === selection.methodology,
    )
  );
}
