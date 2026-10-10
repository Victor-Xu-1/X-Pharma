import { formatDate, StatusBadge } from "../../components/common";
import type { EnterpriseOverviewRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";

export function EnterpriseOverview({ overview }: { overview: EnterpriseOverviewRead }) {
  useLocale();
  const metrics = [
    ["用户总数", overview.user_count],
    ["活跃用户", overview.active_user_count],
    ["管理员", overview.admin_count],
    ["活跃用户组", overview.active_group_count],
    ["业务数据集", overview.dataset_count],
    ["活跃数据源", overview.active_source_count],
    ["24 小时审计事件", overview.audit_event_count_24h],
  ] as const;
  return (
    <>
      <section className="enterprise-metrics" aria-label={t("租户运营指标")}>
        {metrics.map(([label, value]) => (
          <div key={label}>
            <strong>{value}</strong>
            <small>{t(label)}</small>
          </div>
        ))}
      </section>
      <dl className="enterprise-tenant-details">
        <div>
          <dt>{t("租户标识")}</dt>
          <dd>{overview.tenant.slug}</dd>
        </div>
        <div>
          <dt>{t("运行状态")}</dt>
          <dd>
            <StatusBadge value={overview.tenant.active ? "active" : "disabled"} />
          </dd>
        </div>
        <div>
          <dt>{t("创建时间")}</dt>
          <dd>{formatDate(overview.tenant.created_at, true)}</dd>
        </div>
        <div>
          <dt>{t("租户 ID")}</dt>
          <dd className="mono-value">{overview.tenant.id}</dd>
        </div>
      </dl>
    </>
  );
}
