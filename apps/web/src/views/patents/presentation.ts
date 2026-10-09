import { formatDate } from "../../components/common";
import { formattingLocale } from "../../lib/i18n";
import { patentText as t } from "../../lib/i18n/patents";

/** A source calendar date is not a midnight instant in the viewer's timezone. */
export function patentCalendarDate(value: string | null | undefined): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return formatDate(value);
  const date = new Date(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) return "--";
  return new Intl.DateTimeFormat(formattingLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC",
  }).format(date);
}

export function displayPatentList(values: string[], empty = "--", max = 2): string {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join(" · ");
  return values.length > max ? t("{values} 等 {count} 项", { values: visible, count: values.length }) : visible;
}

export function publicationNumbers(values: Array<Record<string, unknown>>): string {
  const identifiers = values
    .map((item) => item.publication_number ?? item.number ?? item.identifier)
    .filter((value): value is string => typeof value === "string" && Boolean(value.trim()));
  return displayPatentList(identifiers, values.length ? t("{count} 项公开", { count: values.length }) : "--");
}
