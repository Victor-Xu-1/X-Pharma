import { formatScientificNumber } from "../../lib/scientificNumber";

/** Plain DOM text keeps source-owned labels literal, without HTML interpolation. */
export function trendTooltip(point: { label: string; value: number }, unit: string): HTMLElement {
  const container = document.createElement("div");
  container.className = "scientific-trend-tooltip";
  const period = document.createElement("div");
  period.textContent = point.label;
  const estimate = document.createElement("strong");
  estimate.textContent = formatScientificNumber(point.value);
  const unitLabel = document.createElement("div");
  unitLabel.textContent = unit;
  container.append(period, estimate, unitLabel);
  return container;
}
