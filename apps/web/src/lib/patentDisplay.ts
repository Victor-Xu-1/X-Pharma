import { patentLegalStatusLabels } from "./contracts/patents";
import { patentText as t } from "./i18n/patents";
import { professionalEnumLabel } from "./i18n/professionalEnums";

/** Translate only the project's explicit status dictionary, never an unknown source code. */
export function patentStatus(value: string | null | undefined, sourceLabel?: string): string {
  if (!value) return t("状态未披露");
  return Object.hasOwn(patentLegalStatusLabels, value)
    ? professionalEnumLabel(patentLegalStatusLabels[value], value)
    : (sourceLabel ?? value);
}
