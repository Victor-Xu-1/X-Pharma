import { type ReactNode, useId, useState } from "react";
import { createPortal } from "react-dom";
import { useLocale } from "../../lib/i18n";
import { type CommercialRecordLabel, commercialRecordText as t } from "../../lib/i18n/commercialRecordDetails";
import { RecordInspectionDialog } from "./RecordInspectionDialog";

/** Expand only on request. Source values remain verbatim and this component performs no reads or writes. */
export function RecordDetails({ name, children }: { name: string; children: ReactNode }) {
  useLocale();
  const id = useId();
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <button
        type="button"
        className="commercial-record-trigger text-button"
        aria-label={t("查看 {name} 的记录详情", { name })}
        aria-haspopup="dialog"
        aria-expanded={expanded}
        aria-controls={expanded ? id : undefined}
        onClick={() => setExpanded(true)}
      >
        {t("记录详情")}
      </button>
      {expanded
        ? createPortal(
            <RecordInspectionDialog id={id} name={name} onClose={() => setExpanded(false)}>
              {children}
            </RecordInspectionDialog>,
            document.body,
          )
        : null}
    </>
  );
}
export function RecordFacts({ fields }: { fields: ReadonlyArray<{ label: CommercialRecordLabel; value: ReactNode }> }) {
  useLocale();
  return (
    <dl className="commercial-record-facts">
      {fields.map(({ label, value }) => (
        <div key={label}>
          <dt>{t(label)}</dt>
          <dd>
            {value == null || value === "" ? t("未上报") : typeof value === "boolean" ? t(value ? "是" : "否") : value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function OriginalRecordValue({ value }: { value: unknown }) {
  return <pre className="commercial-record-value">{JSON.stringify(value, null, 2)}</pre>;
}
export function RecordList({ values }: { values: readonly string[] }) {
  useLocale();
  const occurrences = new Map<string, number>();
  const items = values.map((value) => {
    const occurrence = occurrences.get(value) ?? 0;
    occurrences.set(value, occurrence + 1);
    return { value, key: value + ":" + occurrence };
  });
  return values.length ? (
    <ul className="commercial-record-list">
      {items.map((item) => (
        <li key={item.key}>{item.value}</li>
      ))}
    </ul>
  ) : (
    <span>{t("暂无条目")}</span>
  );
}
