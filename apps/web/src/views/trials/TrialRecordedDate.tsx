import { clinicalText as t } from "../../lib/i18n/clinical";
import { recordedCalendarDate } from "../../lib/recordedCalendarDate";
export function TrialRecordedDate({ value, precision }: { value: string | null; precision: string | null }) {
  if (!value) return <>--</>;
  const formatted = recordedCalendarDate(value, precision);
  if (formatted !== null) return <>{formatted}</>;
  const caption =
    precision === "day"
      ? t("日")
      : precision === "month"
        ? t("月")
        : precision === "year"
          ? t("年")
          : (precision ?? t("未记录"));
  return (
    <span className="table-stacked-copy">
      <span>{value}</span>
      <small>{t("日期精度：{precision}", { precision: caption })}</small>
    </span>
  );
}
