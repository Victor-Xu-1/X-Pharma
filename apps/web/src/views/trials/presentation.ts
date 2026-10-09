import type { ClinicalTrialSearchItemRead } from "../../lib/generated";
import { clinicalText as t } from "../../lib/i18n/clinical";
import { queryText } from "../../lib/i18n/query";
export function displayList(values: string[], empty = "--", max = 2) {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join(queryText("、"));
  return values.length > max ? t("{values} 等 {count} 项", { values: visible, count: values.length }) : visible;
}

export function objectNames(values: Array<Record<string, unknown>>) {
  const names = values
    .map((item) => item.name ?? item.title ?? item.label)
    .filter((value): value is string => typeof value === "string" && Boolean(value.trim()));
  return displayList(names);
}

export function primaryOutcomeSummary(trial: ClinicalTrialSearchItemRead) {
  const outcome = trial.outcomes.find((item) => item.outcome_type?.toUpperCase() === "PRIMARY") ?? trial.outcomes[0];
  const result = outcome?.results?.[0];
  if (!outcome || !result) return t("未报告");
  return `${outcome.measure}: ${result.value}${result.unit ? ` ${result.unit}` : ""}`;
}

export function uniqueValues(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

export function displayBoolean(value: boolean | null | undefined) {
  return value === true ? t("是") : value === false ? t("否") : "--";
}

export function formatResultRange(
  lower: number | null | undefined,
  upper: number | null | undefined,
  dispersion?: string | null,
) {
  const range =
    lower != null && upper != null
      ? `${lower}-${upper}`
      : lower != null
        ? `${t("下限：{value}", { value: lower })} · ${t("上限未记录")}`
        : upper != null
          ? `${t("下限未记录")} · ${t("上限：{value}", { value: upper })}`
          : "";
  return [range, dispersion].filter((value) => value != null && value !== "").join(" · ") || "--";
}
