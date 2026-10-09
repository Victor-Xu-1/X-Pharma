import { formattingLocale } from "../../lib/i18n";

export function formatAttribute(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (["string", "number", "boolean"].includes(typeof value)) return String(value);
  return JSON.stringify(value);
}

export function formatMoney(value: number | null, currency: string | null): string {
  if (value === null) return "--";
  return `${currency ?? ""} ${new Intl.NumberFormat(formattingLocale(), { notation: "compact", maximumFractionDigits: 2 }).format(value)}`.trim();
}
