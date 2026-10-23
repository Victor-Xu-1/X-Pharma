import { formattingLocale } from "./i18n";

/** Preserve the supplied finite estimate; missing values must never become zero. */
export function formatScientificNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat(formattingLocale(), { maximumSignificantDigits: 21 }).format(value);
}
