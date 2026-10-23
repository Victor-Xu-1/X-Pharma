import { EmptyState, formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { DataLifecycleEvent } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import { OriginalRecordValue, RecordDetails, RecordFacts, RecordList } from "../RecordDetails";
export function LifecycleEventRecords({ events }: { events: DataLifecycleEvent[] }) {
  useLocale();
  return (
    <>
      <section className="operations-section">
        <header>
          <div>
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
                    <td className="mono-cell">
                      {item.target_id}
                      <RecordDetails name={item.id}>
                        <RecordFacts
                          fields={[
                            { label: "事件标识", value: item.id },
                            { label: "目标类型", value: item.target_type },
                            { label: "数据类别", value: item.data_class },
                            { label: "操作人", value: item.actor_user_id },
                            { label: "操作键", value: item.idempotency_key },
                            { label: "策略标识", value: item.policy_id },
                            { label: "法律保全标识", value: <RecordList values={item.legal_hold_ids} /> },
                            { label: "原始事件详情", value: <OriginalRecordValue value={item.details} /> },
                          ]}
                        />
                      </RecordDetails>
                    </td>
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
