import { Columns3, X } from "lucide-react";
import { formatDate, Spinner } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { RegulatoryEventSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { type regulatoryMessages, regulatoryText as t } from "../../lib/i18n/regulatory";
import {
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetyStatusLabels,
  severityLabels,
} from "../../lib/regulatoryDisplay";
import { regulatoryValue as displayValue, regulatoryBoolean } from "./presentation";
export function RegulatoryComparison({
  events,
  loading,
  error,
  selectedCount,
  onRemove,
  onClear,
  onOpen,
  onRetry,
}: {
  events: RegulatoryEventSearchItemRead[];
  loading: boolean;
  error: Error | null;
  selectedCount: number;
  onRemove: (eventId: string) => void;
  onClear: () => void;
  onOpen: (eventId: string) => void;
  onRetry: () => void;
}) {
  useLocale();
  const metrics: Array<[keyof typeof regulatoryMessages, (event: RegulatoryEventSearchItemRead) => string]> = [
    ["监管机构 / 辖区", (event) => `${event.agency} / ${event.jurisdiction}`],
    [
      "事件 / 日期",
      (event) => `${displayValue(event.event_type, eventTypeLabels)} / ${formatDate(event.decision_date ?? "")}`,
    ],
    ["认定资格", (event) => displayValue(event.designation_type, designationLabels)],
    [
      "标签",
      (event) =>
        `${displayValue(event.label_change_type, labelChangeLabels)} / ${event.label_version ?? t("版本未披露")}`,
    ],
    ["批准人群", (event) => event.approved_population ?? t("未披露")],
    ["生物标志物", (event) => event.biomarker ?? t("未披露")],
    [
      "给药信息",
      (event) => [event.route_of_administration, event.dosage_form].filter(Boolean).join(" / ") || t("未披露"),
    ],
    ["黑框警告", (event) => regulatoryBoolean(event.has_boxed_warning)],
    [
      "安全信号",
      (event) => `${displayValue(event.safety_term)} / ${displayValue(event.safety_severity, severityLabels)}`,
    ],
    ["信号状态", (event) => displayValue(event.safety_status, safetyStatusLabels)],
    ["风险措施", (event) => event.risk_actions.join("；") || t("未披露")],
    ["来源更新", (event) => formatDate(event.source_updated_at ?? "", true)],
  ];

  return (
    <section className="regulatory-comparison" aria-label={t("监管事件对比")}>
      <header>
        <div>
          <Columns3 size={17} />
          <strong>{t("监管事件对比")}</strong>
          <span>{selectedCount}/4</span>
        </div>
        <button className="secondary-button" type="button" onClick={onClear}>
          {t("清空对比")}
        </button>
      </header>
      {loading && !events.length ? <Spinner label={t("正在加载对比事件")} /> : null}
      {loading && events.length ? <p role="status">{t("正在刷新对比事件")}</p> : null}
      {error ? (
        <p className="form-error" role="alert">
          {error.message || t("对比事件加载失败")}
          {events.length ? <span>{t("显示上次可用的对比事件")}</span> : null}
          <button type="button" className="secondary-button" disabled={loading} onClick={onRetry}>
            {t("重试对比读取")}
          </button>
        </p>
      ) : null}
      {events.length ? (
        <ScrollableTableRegion className="regulatory-comparison-scroll" ariaLabel={t("监管对比表滚动区域")}>
          <table className="comparison-table regulatory-comparison-table" aria-label={t("监管事件对比")}>
            <thead>
              <tr>
                <th>{t("比较维度")}</th>
                {events.map((event) => (
                  <th key={event.id}>
                    <button type="button" onClick={() => onOpen(event.id)}>
                      {event.subject_entity.name}
                    </button>
                    <small>{event.event_identifier}</small>
                    <button
                      className="icon-button"
                      type="button"
                      aria-label={t("移除 {title}", { title: event.title })}
                      title={t("移除对比")}
                      onClick={() => onRemove(event.id)}
                    >
                      <X size={14} />
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map(([label, render]) => (
                <tr key={label}>
                  <th>{t(label)}</th>
                  {events.map((event) => (
                    <td key={event.id}>{render(event)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : null}
    </section>
  );
}
