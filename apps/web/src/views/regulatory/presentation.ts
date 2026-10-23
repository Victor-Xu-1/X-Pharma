import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import { regulatoryText as t } from "../../lib/i18n/regulatory";

/** Only existing application-owned enum captions; unknown source codes stay literal. */
export function regulatoryValue(value: string | null | undefined, labels?: Readonly<Record<string, string>>): string {
  if (value === null || value === undefined || value === "") return t("未披露");
  return labels && Object.hasOwn(labels, value) ? professionalEnumLabel(labels[value], value) : value;
}

export function regulatoryLabels(labels: Readonly<Record<string, string>>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(labels).map(([code, caption]) => [code, professionalEnumLabel(caption, code)]),
  );
}

export function regulatoryBoolean(value: boolean | null | undefined): string {
  return value === true ? t("有") : value === false ? t("无") : t("未披露");
}
