import { formattingLocale, useMessages } from "../../lib/i18n";
import { monitoringMessages } from "../../lib/i18n/monitoring";

/** Native disclosure preserves open state across locale without another query owner. */
export function MonitoringConditions({ conditions }: { conditions: readonly string[] }) {
  const text = useMessages(monitoringMessages);
  if (!conditions.length) return null;
  return (
    <details className="monitoring-record-description monitoring-record-conditions">
      <summary title={conditions.join(" · ")}>
        {text("{count} 个条件", { count: new Intl.NumberFormat(formattingLocale()).format(conditions.length) })}
      </summary>
      <ul aria-label={text("全部检索条件")}>
        {conditions.map((condition) => (
          <li key={condition}>{condition}</li>
        ))}
      </ul>
    </details>
  );
}
