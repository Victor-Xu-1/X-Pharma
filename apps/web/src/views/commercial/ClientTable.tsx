import { Ban, Power } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CommercialClient } from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialRecordText } from "../../lib/i18n/commercialRecordDetails";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { RecordDetails, RecordFacts } from "./RecordDetails";
import type { ClientAction } from "./types";

export function ClientTable({
  items,
  busy,
  onAction,
}: {
  items: CommercialClient[];
  busy: string;
  onAction: (action: ClientAction) => void;
}) {
  useLocale();
  if (!items.length) return <EmptyState title={t("暂无 Agent 客户端")} />;
  return (
    <ScrollableTableRegion className="commercial-table" ariaLabel={t("Agent 客户端滚动区域")}>
      <table aria-label={t("Agent 客户端")}>
        <thead>
          <tr>
            <th>{t("客户端")}</th>
            <th>{t("订阅")}</th>
            <th>{t("计费账户")}</th>
            <th>{t("状态")}</th>
            <th>{t("主体")}</th>
            <th>{t("可用额度")}</th>
            <th>{t("活跃预留")}</th>
            <th>{t("24h 拒绝")}</th>
            <th>{t("最近策略事件")}</th>
            <th>{t("操作")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.display_name}</strong>
                <span className="cell-subtitle mono-cell">{item.client_key}</span>
                <RecordDetails name={item.display_name}>
                  <RecordFacts
                    fields={[
                      { label: "客户端标识", value: item.id },
                      { label: "订阅状态", value: item.subscription_status },
                      { label: "创建时间", value: formatDate(item.created_at, true) },
                    ]}
                  />
                  {item.subjects.length ? (
                    item.subjects.map((subject) => (
                      <RecordFacts
                        key={subject.actor_type + ":" + subject.subject_id}
                        fields={[
                          { label: "主体标识", value: subject.subject_id },
                          { label: "主体类型", value: subject.actor_type },
                          { label: "已启用", value: subject.active },
                        ]}
                      />
                    ))
                  ) : (
                    <p>{commercialRecordText("暂无主体")}</p>
                  )}
                </RecordDetails>
              </td>
              <td className="mono-cell">{item.subscription_key ?? "--"}</td>
              <td className="mono-cell">{item.billing_account_key ?? "--"}</td>
              <td>
                <StatusBadge value={item.active ? "active" : "revoked"} />
              </td>
              <td>{item.subjects.filter((subject) => subject.active).length}</td>
              <td>{item.available_units ?? "--"}</td>
              <td>{item.active_reservations}</td>
              <td className={item.denial_count_24h ? "danger-text" : ""}>{item.denial_count_24h}</td>
              <td>{formatDate(item.last_policy_event_at, true)}</td>
              <td>
                <button
                  className={item.active ? "icon-button danger-text" : "icon-button"}
                  type="button"
                  disabled={Boolean(busy)}
                  title={item.active ? t("停用客户端") : t("重新启用")}
                  aria-label={
                    item.active
                      ? t("停用 {name}", { name: item.display_name })
                      : t("启用 {name}", { name: item.display_name })
                  }
                  onClick={() => onAction({ client: item, active: !item.active })}
                >
                  {item.active ? <Ban size={17} /> : <Power size={17} />}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
