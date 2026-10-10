import { EmptyState, formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { DataLifecycleEvent } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
export function LifecycleEventRecords({ events }: { events: DataLifecycleEvent[] }) {
  useLocale();
  return (
    <>
      <section className="operations-section">
        <header>
          <div>
            <p className="eyebrow">IMMUTABLE AUDIT</p>
            <h2>{t("生命周期审计")}</h2>
          </div>
        </header>
        {!events.length ? (
          <EmptyState title={t("暂无生命周期执行事件")} />
        ) : (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("生命周期审计滚动区域")}>
            <table aria-label={t("生命周期审计")}>
              <thead>
                <tr>
                  <th>{t("时间")}</th>
                  <th>{t("目标")}</th>
                  <th>{t("动作")}</th>
                  <th>{t("结果")}</th>
                  <th>{t("策略版本")}</th>
                  <th>{t("原因")}</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDate(item.created_at, true)}</td>
                    <td className="mono-cell">{item.target_id}</td>
                    <td>{item.action}</td>
                    <td>
                      <StatusBadge value={item.outcome} />
                    </td>
                    <td>v{item.policy_version}</td>
                    <td>{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        )}
      </section>
    </>
  );
}
