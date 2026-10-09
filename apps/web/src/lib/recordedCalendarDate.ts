import { getLocale } from "./i18n";

const precisions = new Set(["day", "month", "year"]);
/** Only a recorded calendar date and its declared precision are formatted; no local-time conversion. */
export function recordedCalendarDate(value: string, precision: unknown): string | null {
  if (typeof precision !== "string" || !precisions.has(precision)) return null;
  const match = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?(?:T00:00:00(?:\.0+)?(?:Z|\+00:00))?$/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  if (value.includes("T") && !day) return null;
  if (day) {
    const calendar = `${year}-${month}-${day}`;
    const parsed = new Date(`${calendar}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== calendar) return null;
  } else if (month && (Number(month) < 1 || Number(month) > 12)) return null;
  if (precision === "year") return getLocale() === "en" ? year : `${year}年`;
  if (!month) return null;
  if (precision === "month") return getLocale() === "en" ? `${year}-${month}` : `${year}年${month}月`;
  return day ? (getLocale() === "en" ? `${year}-${month}-${day}` : `${year}年${month}月${day}日`) : null;
}
