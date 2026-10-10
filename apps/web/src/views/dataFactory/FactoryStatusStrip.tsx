import { formatDate, statusLabel } from "../../components/common";
import type {
  DataSource,
  DataSourceReadiness,
  IngestionCapabilities,
  IngestionRun,
} from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";

export function FactoryStatusStrip({
  sources,
  readiness,
  capabilities,
  latestRun,
  stale,
}: {
  sources: readonly DataSource[];
  readiness: readonly DataSourceReadiness[];
  capabilities: IngestionCapabilities;
  latestRun?: IngestionRun;
  stale: boolean;
}) {
  useLocale();
  const observed = sources.flatMap((source) => {
    const report = readiness.find((item) => item.source_id === source.id);
    return report ? [report] : [];
  });
  const ready = observed.filter((item) => item.operational_status === "ready").length;
  const active = sources.filter((source) => source.state === "active").length;
  const unknown = sources.length - observed.length;
  return (
    <>
      {stale ? <p className="field-help">{t("上次读取的状态")}</p> : null}
      <section className="factory-status-strip" aria-label={t("自动入库运行状态")}>
        <div>
          <span>{t("自动数据源")}</span>
          <strong>{sources.length}</strong>
          <small>{t("{active} 已启用 · {ready} 就绪", { active, ready })}</small>
          {unknown > 0 ? <small>{t("{count} 个来源未观测到就绪状态", { count: unknown })}</small> : null}
        </div>
        <div>
          <span>{t("第三方 LLM API")}</span>
          <strong>
            {t(
              capabilities.ai_model_configured
                ? capabilities.ai_governance_enabled
                  ? "远程 API 已配置"
                  : "已配置但未启用"
                : "待配置",
            )}
          </strong>
          <small>
            {capabilities.ai_model ? t("远程 API · {model}", { model: capabilities.ai_model }) : t("未绑定第三方API")}
          </small>
        </div>
        <div>
          <span>{t("最近运行")}</span>
          <strong>{latestRun ? statusLabel(latestRun.effective_state) : t("暂无")}</strong>
          <small>{latestRun ? formatDate(latestRun.created_at, true) : t("等待数据源")}</small>
        </div>
      </section>
    </>
  );
}
