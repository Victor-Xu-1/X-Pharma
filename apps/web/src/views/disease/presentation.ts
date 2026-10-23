import { formatDate } from "../../components/common";
import type { EpidemiologyObservationSearchItemRead } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";

export function formatNumber(value: number | null | undefined) {
  return value == null
    ? "--"
    : new Intl.NumberFormat(formattingLocale(), { maximumSignificantDigits: 21 }).format(value);
}

export function periodLabel(item: EpidemiologyObservationSearchItemRead) {
  return item.period_start === item.period_end
    ? formatDate(item.period_end)
    : `${formatDate(item.period_start)} - ${formatDate(item.period_end)}`;
}
